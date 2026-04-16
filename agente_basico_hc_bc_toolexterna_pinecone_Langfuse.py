"""
Agente IA Completo: Base de Conocimiento + Internet + Histórico + Langfuse
- Tool 1: Base de Conocimiento (RAG con Pinecone)
- Tool 2: Búsqueda en Internet (Tavily)
- Histórico: Guarda conversaciones en PostgreSQL
- Observabilidad: Langfuse (trazas, tokens, costos, latencia)

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import sys
import uuid
from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Agregar el directorio actual al path para importar tools (portable para despliegue)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_postgres import PostgresChatMessageHistory
import psycopg

# LANGFUSE ▶ Importar cliente singleton, decorador @observe y propagación de atributos
from langfuse import Langfuse, get_client, observe, propagate_attributes
# LANGFUSE ▶ Importar el CallbackHandler que intercepta todas las llamadas de LangChain
from langfuse.langchain import CallbackHandler

# Importar tools desde la carpeta tools/
from tools.Base_de_conocimiento import buscar_datapath
from tools.Busqueda_internet import buscar_internet
from tools.Hora_y_fecha import obtener_fecha_hora

# Importar guardrail de entrada (Capa 1 de Seguridad)
from guardrails.input_guardrail import verificar_input_guardrail, respuesta_bloqueada

# Importar evaluador LLM-as-a-Judge (módulo evaluation/)
from evaluation.llm_judge import evaluar_con_llm_judge

# ============================================
# 1. CONFIGURACIÓN DE BASE DE DATOS (Histórico)
# ============================================
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

if not all([DB_USER, DB_PASSWORD, DB_HOST]):
    raise ValueError(
        "❌ Faltan variables de base de datos en .env\n"
        "Requeridas: DB_USER, DB_PASSWORD, DB_HOST"
    )

DATABASE_URL = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"🔌 Conectando como: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# ============================================
# LANGFUSE: INICIALIZACIÓN DEL CLIENTE
# ============================================
# LANGFUSE ▶ Lee LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY y LANGFUSE_BASE_URL desde .env
# LANGFUSE ▶ Crea el cliente Singleton una sola vez al arrancar el módulo
Langfuse()
# LANGFUSE ▶ get_client() devuelve la instancia Singleton ya inicializada
langfuse_client = get_client()
print(f"📊 Langfuse conectado: {os.getenv('LANGFUSE_BASE_URL', 'https://cloud.langfuse.com')}")

# ============================================
# 2. LISTA DE TOOLS DISPONIBLES
# ============================================
tools = [
    buscar_datapath,      # Base de conocimiento DATAPATH
    buscar_internet,      # Búsqueda en internet (Tavily)
    obtener_fecha_hora,   # Fecha y hora actual por zona horaria
]

# ============================================
# 3. CONFIGURACIÓN DEL MODELO CON TOOLS
# ============================================
chat = init_chat_model("gpt-4.1", temperature=0.7)
chat_con_tools = chat.bind_tools(tools)

# ============================================
# 4. PROMPT DEL AGENTE + CONTEXTO FECHA/HORA
# ============================================
AGENT_TIMEZONE = os.getenv("AGENT_TIMEZONE", "America/Lima")


def _contexto_fecha_hora() -> str:
    """Fecha y hora actual para inyectar en el system prompt (cada turno)."""
    try:
        tz = ZoneInfo(AGENT_TIMEZONE)
    except Exception:
        tz = ZoneInfo("America/Lima")
    now = datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S") + f" (zona {AGENT_TIMEZONE})"



# system_prompt = """Eres DataBot, el asistente virtual oficial de DATAPATH — escuela de formación en Inteligencia Artificial y tecnología.

# Tu ÚNICO propósito es responder consultas relacionadas con DATAPATH: programas, cursos, precios, modalidades, docentes, inscripciones, fechas de inicio, beneficios y cualquier información institucional.

# Al inicio de cada turno se te indica la FECHA Y HORA ACTUAL; úsala cuando la respuesta dependa de "hoy", "ahora", "esta semana", horarios o plazos. Para otras zonas horarias usa la tool obtener_fecha_hora.

# <Herramientas>
# 1. buscar_datapath: Para información interna de DATAPATH (programas, cursos, precios, docentes, inscripciones)
# 2. buscar_internet: Para buscar información de DATAPATH en internet (reseñas, menciones, comparativas del sector de formación en IA en Perú). La búsqueda siempre se realiza en el contexto de DATAPATH automáticamente.
# 3. obtener_fecha_hora: Para la fecha y hora actual
# 4. transferir_a_humano: Para transferir la conversación a un asesor humano y desactivar la IA
# </Herramientas>

# <Instrucciones>
# - Para preguntas sobre DATAPATH → USA buscar_datapath PRIMERO; si no hay suficiente info, complementa con buscar_internet
# - Para "qué hora es", "qué día es hoy" → USA obtener_fecha_hora
# - Para saludos y despedidas → Responde directamente, pero redirige amablemente al tema DATAPATH
# - NUNCA respondas preguntas de cultura general, noticias, política, deportes, ciencia u otros temas ajenos a DATAPATH
# - Si la pregunta no es sobre DATAPATH, rechaza amablemente usando el Mensaje de Rechazo
# - Recuerdas toda la conversación gracias a tu memoria persistente
# - Responde siempre en español de manera clara, profesional y amigable
# - Si el usuario pide hablar con un humano, asesor o representante → USA transferir_a_humano INMEDIATAMENTE y luego informa al usuario que un asesor le atenderá pronto
# </Instrucciones>

# <Ejemplos_Si>
# - "Hola" → Saluda y ofrece ayuda con DATAPATH
# - "¿Qué cursos tienen?" → Usa buscar_datapath
# - "¿Cuánto cuesta el programa de IA?" → Usa buscar_datapath
# - "¿Cuándo empieza el próximo módulo?" → Usa buscar_datapath + obtener_fecha_hora
# - "¿Tienen buenas reseñas?" → Usa buscar_internet
# - "Quiero hablar con un asesor" → Usa transferir_a_humano
# - "Necesito atención personalizada / un humano / una persona real" → Usa transferir_a_humano
# </Ejemplos_Si>

# <Ejemplos_No>
# - "¿Qué día son las elecciones en Perú?" → Rechaza: no es un tema de DATAPATH
# - "¿Qué pasó hoy en las noticias?" → Rechaza: no es un tema de DATAPATH
# - "¿Cuál es la capital de Francia?" → Rechaza: no es un tema de DATAPATH
# - "Explícame cómo funciona Python" → Rechaza: para eso están los cursos de DATAPATH
# </Ejemplos_No>

# <Mensaje_de_Rechazo>
# Esa consulta está fuera de mi ámbito. Soy DataBot y estoy especializado en información sobre los programas y servicios de DATAPATH. ¿Te puedo ayudar con información sobre nuestros cursos, precios, fechas de inicio o inscripciones?
# </Mensaje_de_Rechazo>"""



# ============================================
# ALTERNATIVA: PROMPT DESDE LANGFUSE (Prompt Management)
# --------------------------------------------
# Para usarlo:
#   1. Ve a Langfuse UI → Prompts → Create Prompt
#   2. Nombre: "databot-system-prompt"   Tipo: text
#   3. Pega el contenido del system_prompt de arriba
#   4. Asigna el label "production"
#   5. Comenta el bloque system_prompt = """...""" de arriba
#   6. Descomenta el bloque de abajo
#
# Ventaja: puedes cambiar el prompt desde la UI sin tocar código ni reiniciar el servidor
# Desventaja: el prompt sale del repo y no puedes editarlo con vibe coding en Cursor
# ============================================
lf_prompt = langfuse_client.get_prompt("Prompt-del-Agente-para-Whatsapp-v2")
system_prompt = lf_prompt.compile()   # sin variables; si tuvieras usa compile(var=valor)
print(f"📝 Prompt cargado desde Langfuse: versión {lf_prompt.version}")

# ============================================
# 5. CREAR TABLA DE HISTORIAL
# ============================================
def crear_tabla_historial():
    try:
        sync_connection = psycopg.connect(DATABASE_URL)
        PostgresChatMessageHistory.create_tables(sync_connection, "chat_history")
        sync_connection.close()
    except Exception as e:
        print(f"⚠️ Nota sobre tabla: {e}")

crear_tabla_historial()

# ============================================
# 6. HISTÓRICO DE CONVERSACIÓN
# ============================================
def get_session_history(session_id: str) -> PostgresChatMessageHistory:
    sync_connection = psycopg.connect(DATABASE_URL)
    return PostgresChatMessageHistory(
        "chat_history",
        session_id,
        sync_connection=sync_connection
    )

# ============================================
# 7. FUNCIÓN DE CHAT CON AGENTE + TOOLS + LANGFUSE
# ============================================
# LANGFUSE ▶ @observe() convierte esta función en un Trace raíz en Langfuse.
#             Cada llamada a chat_con_agente() generará una traza independiente
#             que agrupa todas las observaciones del turno (LLM calls, tools, etc.)
@observe()
def chat_con_agente(
    mensaje_usuario: str,
    session_id: str,
    tools_extra: list | None = None,
) -> str:
    """
    Ejecuta el agente con tools y memoria.
    El agente decide si usar herramientas o responder directamente.

    Args:
        mensaje_usuario: Mensaje del usuario.
        session_id:      UUID de la sesión/conversación (para historial).
        tools_extra:     Tools adicionales por turno (ej. transferir_a_humano
                         con contact_id inyectado desde el webhook).
    """
    # ── Capa 1 de Seguridad: Guardrail de Entrada ──────────────────
    es_seguro, motivo = verificar_input_guardrail(mensaje_usuario)
    if not es_seguro:
        print(f"🚨 [GUARDRAIL] Mensaje bloqueado. Motivo: {motivo}")
        # LANGFUSE v4 ▶ propagate_attributes() reemplaza update_current_trace() para
        #               atributos de correlación (tags, session_id, etc.)
        with propagate_attributes(
            trace_name="databot-guardrail-bloqueado",  # LANGFUSE v4 ▶ 'name' ahora es 'trace_name'
            session_id=session_id,
            tags=["guardrail", "bloqueado"],
        ):
            pass
        # LANGFUSE v4 ▶ set_current_trace_io()
        langfuse_client.set_current_trace_io(
            input={"mensaje": mensaje_usuario},
            output={"bloqueado": "true", "motivo": motivo},
        )
        return respuesta_bloqueada(motivo)
    # ───────────────────────────────────────────────────────────────

    # Combinar tools base con tools dinámicas del turno
    tools_turno = tools + (tools_extra or [])
    chat_turno = chat.bind_tools(tools_turno)

    # LANGFUSE ▶ Crear el CallbackHandler que intercepta cada llamada al LLM de LangChain.
    #             Al crearse dentro del contexto de @observe(), hereda automáticamente
    #             el trace padre y anida todas las observaciones bajo él.
    langfuse_handler = CallbackHandler()

    # Obtener historial
    history = get_session_history(session_id)
    mensajes_previos = history.messages

    # Construir mensajes para el modelo (inyectamos fecha/hora actual en cada turno)
    system_content = (
        system_prompt
        + "\n\n---\nFECHA Y HORA ACTUAL (referencia para este turno): "
        + _contexto_fecha_hora()
    )
    messages = [{"role": "system", "content": system_content}]

    # Agregar historial
    for msg in mensajes_previos:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content})

    # Agregar mensaje actual
    messages.append({"role": "user", "content": mensaje_usuario})

    # LANGFUSE v4 ▶ propagate_attributes() es el único método para atributos de correlación.
    #               En v4, 'update_current_trace()' fue eliminado; los atributos ahora viven
    #               en cada observación hija, no solo en el trace padre.
    #               trace_name: nombre visible en el dashboard (antes era 'name' en update_current_trace)
    #               metadata debe ser dict[str, str] con valores ≤ 200 chars (restricción de v4)
    with propagate_attributes(
        trace_name="databot-turno",                          # LANGFUSE v4 ▶ nombre del trace en el dashboard
        session_id=session_id,                               # LANGFUSE v4 ▶ agrupa trazas por conversación
        user_id=f"conv-{session_id[:8]}",                    # LANGFUSE v4 ▶ identifica al usuario en métricas
        tags=["produccion", "chatwoot", "databot"],          # LANGFUSE v4 ▶ etiquetas para filtrar
        metadata={"modelo": "gpt-4.1"},                      # LANGFUSE v4 ▶ dict[str,str] obligatorio en v4
    ):
        # LANGFUSE ▶ config={"callbacks": [langfuse_handler]} activa el tracing en esta
        #             invocación: captura el prompt, la respuesta, los tokens y la latencia.
        response = chat_turno.invoke(messages, config={"callbacks": [langfuse_handler]})

        # Procesar tool calls si existen
        if response.tool_calls:
            tool_results = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                for t in tools_turno:
                    if t.name == tool_name:
                        result = t.invoke(tool_args)
                        tool_results.append({
                            "tool_call_id": tool_call["id"],
                            "result": result,
                        })
                        break

            messages.append(response)
            for tr in tool_results:
                messages.append(ToolMessage(
                    content=tr["result"],
                    tool_call_id=tr["tool_call_id"],
                ))

            # LANGFUSE ▶ Segunda llamada al LLM (respuesta final tras ejecutar tools).
            #             También trackeada: captura tokens de la respuesta final.
            final_response = chat_turno.invoke(messages, config={"callbacks": [langfuse_handler]})
            respuesta_final = final_response.content
        else:
            respuesta_final = response.content

    # LANGFUSE v4 ▶ set_current_trace_io()
    #               Registra el input/output del turno completo a nivel del trace raíz.
    langfuse_client.set_current_trace_io(
        input={"mensaje_usuario": mensaje_usuario},   # LANGFUSE v4 ▶ input del trace principal
        output={"respuesta": respuesta_final},        # LANGFUSE v4 ▶ output del trace principal
    )

    # JUDGE ▶ Obtener el trace_id del turno actual (disponible dentro del contexto @observe())
    #          y disparar la evaluación LLM-as-a-Judge (módulo evaluacion/llm_judge.py).
    #          Los scores quedan vinculados a este trace en el dashboard de Langfuse.
    trace_id_actual = langfuse_client.get_current_trace_id()
    if trace_id_actual:
        evaluar_con_llm_judge(mensaje_usuario, respuesta_final, trace_id_actual)

    # Guardar en historial
    history.add_user_message(mensaje_usuario)
    history.add_ai_message(respuesta_final)

    return respuesta_final


# ============================================
# 8. LOOP DE CONVERSACIÓN
# ============================================
def main():
    print("=" * 60)
    print("🤖 DataBot - Agente COMPLETO (BC + Internet + Memoria)")
    print("=" * 60)
    print("🔧 Tools disponibles:")
    for t in tools:
        print(f"   - {t.name}")
    print("💾 Historial: PostgreSQL")
    
    # Menú de sesión
    print("\nOpciones de sesión:")
    print("  1. Nueva conversación")
    print("  2. Continuar sesión existente (pegar UUID)")
    
    opcion = input("\nElige (1/2): ").strip()
    
    if opcion == "2":
        session_id = input("Pega el UUID de la sesión: ").strip()
        try:
            uuid.UUID(session_id)
        except ValueError:
            print("⚠️ UUID inválido. Creando nueva sesión...")
            session_id = str(uuid.uuid4())
    else:
        session_id = str(uuid.uuid4())
    
    print(f"\n📝 Session ID: {session_id}")
    print("   (Guarda este ID para continuar después)")
    print("✅ El agente puede buscar en DATAPATH y en INTERNET")
    print("Escribe 'salir' para volver al menú.\n")
    
    while True:
        usuario = input("Tú: ").strip()
        
        if usuario.lower() in ['salir', 'exit', 'quit']:
            print(f"\n💾 Tu sesión está guardada.")
            print(f"   UUID: {session_id}")
            # LANGFUSE ▶ flush() fuerza el envío de todos los eventos pendientes a Langfuse
            #             antes de cerrar el proceso. Esencial en scripts de vida corta.
            langfuse_client.flush()
            print("👋 ¡Hasta luego!")
            break
        
        if not usuario:
            continue
        
        try:
            respuesta = chat_con_agente(usuario, session_id)
            print(f"\n🤖 DataBot: {respuesta}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
