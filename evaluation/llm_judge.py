"""
LLM-as-a-Judge: evaluación automática de respuestas de DataBot.

Usa un LLM barato (GPT-4o-mini) para evaluar cada respuesta del agente en cinco
dimensiones y envía los scores a Langfuse.

Scores registrados:
  - relevancia-datapath : ¿La respuesta habló solo de DATAPATH?
  - calidad-respuesta   : ¿Fue útil, clara y correcta?
  - alucinacion         : ¿Inventó datos que no puede conocer (precios, fechas)?
  - llamada-a-accion    : ¿Invitó al usuario a dar el siguiente paso comercial?
  - rechazo-correcto    : ¿Rechazó bien preguntas fuera del ámbito de DATAPATH?

Diseño intencionado:
- Módulo independiente: no importa nada del agente, solo Langfuse y LangChain.
- Cliente Langfuse obtenido con get_client() (singleton, ya inicializado en el agente).
- Silencioso: cualquier fallo del juez es capturado con try/except para no
  interrumpir la conversación del usuario.

Uso desde el agente:
    from evaluation.llm_judge import evaluar_con_llm_judge
    ...
    trace_id = langfuse_client.get_current_trace_id()
    if trace_id:
        evaluar_con_llm_judge(mensaje_usuario, respuesta_final, trace_id)
"""

import json

from langchain.chat_models import init_chat_model
from langfuse import get_client

# ============================================
# MODELO JUEZ
# ============================================
# Usamos GPT-4o-mini para mantener el costo de evaluación bajo.
# Temperatura 0 para respuestas deterministas y JSON consistente.
_chat_judge = init_chat_model("gpt-4o-mini", temperature=0)

# ============================================
# PROMPT DEL JUEZ
# ============================================
# Pide un JSON con exactamente 6 campos. Las llaves dobles {{ }} son
# literales en str.format() (escapan las llaves del JSON de la respuesta).
_JUDGE_PROMPT = """Eres un evaluador experto de chatbots de atención al cliente.

Evalúa la siguiente interacción del chatbot DataBot de DATAPATH (escuela de IA en Perú).

MENSAJE DEL USUARIO:
{mensaje}

RESPUESTA DEL BOT:
{respuesta}

Evalúa en cinco dimensiones y responde ÚNICAMENTE con JSON válido (sin markdown, sin explicaciones extra):
{{
  "relevancia": <float 0.0-1.0>,
  "calidad": <float 0.0-1.0>,
  "alucinacion": <float 0.0-1.0>,
  "llamada_accion": <float 0.0-1.0>,
  "rechazo_correcto": <float 0.0-1.0>,
  "razon": "<máximo 100 caracteres>"
}}

Definiciones:
- relevancia:       ¿La respuesta está enfocada en DATAPATH? 0=nada relevante, 1=totalmente relevante
- calidad:          ¿La respuesta es útil, clara y correcta? 0=pésima, 1=excelente
- alucinacion:      ¿El bot inventó datos específicos que no puede conocer (precios exactos, fechas, nombres de docentes, porcentajes)? 0=no inventó nada, 1=inventó datos concretos. Si la pregunta no aplica, pon 0.
- llamada_accion:   ¿La respuesta invitó al usuario a dar un siguiente paso comercial (inscribirse, contactar asesor, pedir temario, visitar web)? 0=no hubo llamada a la acción, 1=llamada a la acción clara y natural. Si la pregunta no aplica (ej. saludo simple), pon 0.5.
- rechazo_correcto: Si el usuario preguntó algo fuera del ámbito de DATAPATH, ¿el bot lo rechazó correctamente con amabilidad? 0=respondió sin rechazar (MAL), 1=rechazó correctamente (BIEN). Si la pregunta SÍ era sobre DATAPATH, pon 1.
- razon:            Razón breve que justifica los puntajes más bajos o llamativos"""


# ============================================
# FUNCIÓN PÚBLICA
# ============================================
def evaluar_con_llm_judge(
    mensaje_usuario: str,
    respuesta_final: str,
    trace_id: str,
) -> None:
    """
    Evalúa la respuesta de DataBot con un LLM juez y envía los scores a Langfuse.

    Scores que se registran (todos float 0-1):
      - "relevancia-datapath" : ¿La respuesta habló solo de DATAPATH?
      - "calidad-respuesta"   : ¿Fue útil, clara y correcta?
      - "alucinacion"         : ¿Inventó precios, fechas u otros datos concretos?
      - "llamada-a-accion"    : ¿Invitó al usuario a inscribirse o contactar a DATAPATH?
      - "rechazo-correcto"    : ¿Rechazó bien preguntas fuera del ámbito de DATAPATH?

    Todos los scores quedan visibles en:
      Langfuse UI → Tracing → (click en el trace) → sección Scores
      Langfuse UI → Evaluation → Scores → Analytics

    Args:
        mensaje_usuario: El mensaje que envió el usuario en este turno.
        respuesta_final: La respuesta que generó el agente.
        trace_id:        El trace_id de Langfuse del turno actual.
    """
    try:
        # Construir el prompt con los datos del turno actual
        prompt_eval = _JUDGE_PROMPT.format(
            mensaje=mensaje_usuario,
            respuesta=respuesta_final,
        )

        # Llamar al LLM juez SIN callbacks de Langfuse: esta llamada interna
        # no debe aparecer en el trace del usuario para no generar ruido en el dashboard
        eval_response = _chat_judge.invoke([{"role": "user", "content": prompt_eval}])

        # Parsear el JSON devuelto por el juez y sanear todos los valores entre 0 y 1
        eval_data        = json.loads(eval_response.content.strip())
        relevancia       = max(0.0, min(1.0, float(eval_data.get("relevancia",       0.0))))
        calidad          = max(0.0, min(1.0, float(eval_data.get("calidad",          0.0))))
        alucinacion      = max(0.0, min(1.0, float(eval_data.get("alucinacion",      0.0))))
        llamada_accion   = max(0.0, min(1.0, float(eval_data.get("llamada_accion",   0.0))))
        rechazo_correcto = max(0.0, min(1.0, float(eval_data.get("rechazo_correcto", 1.0))))
        razon            = str(eval_data.get("razon", ""))[:100]

        # Obtener el cliente Langfuse (singleton ya inicializado en el agente)
        lf = get_client()

        # Langfuse v4: método create_score() — enviar los 5 scores al trace actual
        lf.create_score(
            trace_id=trace_id,
            name="relevancia-datapath",
            value=relevancia,
            data_type="NUMERIC",
            comment=razon,
        )
        lf.create_score(
            trace_id=trace_id,
            name="calidad-respuesta",
            value=calidad,
            data_type="NUMERIC",
            comment=razon,
        )
        # alucinacion: 0=no inventó nada (bueno), 1=inventó datos (malo)
        lf.create_score(
            trace_id=trace_id,
            name="alucinacion",
            value=alucinacion,
            data_type="NUMERIC",
            comment=razon,
        )
        # llamada-a-accion: 0=no invitó a nada, 1=llamada a la acción clara
        lf.create_score(
            trace_id=trace_id,
            name="llamada-a-accion",
            value=llamada_accion,
            data_type="NUMERIC",
            comment=razon,
        )
        # rechazo-correcto: 1=rechazó bien (o era pregunta válida), 0=respondió sin rechazar
        lf.create_score(
            trace_id=trace_id,
            name="rechazo-correcto",
            value=rechazo_correcto,
            data_type="NUMERIC",
            comment=razon,
        )

        print(
            f"   📊 [JUDGE] "
            f"relevancia={relevancia:.2f} | "
            f"calidad={calidad:.2f} | "
            f"alucinacion={alucinacion:.2f} | "
            f"cta={llamada_accion:.2f} | "
            f"rechazo={rechazo_correcto:.2f} | "
            f"{razon[:50]}"
        )

    except Exception as e:
        # Si el juez falla (timeout, JSON malformado, API error, etc.)
        # el agente NO se cae; simplemente se omite la evaluación de este turno
        print(f"   ⚠️ [JUDGE] Evaluación omitida: {e}")
