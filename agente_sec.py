"""
Agente IA Completo: Base de Conocimiento + Internet + Histórico
- Tool 1: Base de Conocimiento (RAG con Pinecone)
- Tool 2: Búsqueda en Internet (Tavily)
- Histórico: Guarda conversaciones en PostgreSQL

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import sys
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Agregar el directorio actual al path para importar tools (portable para despliegue)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

# Importar tools desde la carpeta tools/
from tools.Base_de_conocimiento import buscar_datapath
from tools.Busqueda_internet import buscar_internet
from tools.Hora_y_fecha import obtener_fecha_hora

# Importar guardrail de entrada (Capa 1 de Seguridad)
from guardrails.input_guardrail import verificar_input_guardrail, respuesta_bloqueada

# Importar el PIIMiddleware nativo de LangChain (guardrails/middleware.py)
from guardrails.middleware import crear_pii_middlewares

# Importar histórico de conversación (PostgreSQL) desde chat_history/
from chat_history import crear_tabla_historial, get_session_history

# Importar config del modelo y system prompt (desacoplados del código)
from model_config import load_model_config
from prompt import load_system_prompt

# ============================================
# 1. LISTA DE TOOLS DISPONIBLES
# ============================================
tools = [
    buscar_datapath,      # Base de conocimiento DATAPATH
    buscar_internet,      # Búsqueda en internet (Tavily)
    obtener_fecha_hora,   # Fecha y hora actual por zona horaria
]

# ============================================
# 2. CONFIGURACIÓN DEL MODELO CON TOOLS
# ============================================
# La config del LLM vive en model_config/model.yaml
_model_cfg = load_model_config()
chat = init_chat_model(
    _model_cfg["llm"]["model"],
    temperature=_model_cfg["llm"]["temperature"],
)

# ============================================
# 3. PROMPT DEL AGENTE + CONTEXTO FECHA/HORA
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


# El system prompt vive en prompt/system_prompt.yaml
system_prompt = load_system_prompt()

# ============================================
# 4. CREAR TABLA DE HISTORIAL (chat_history/)
# ============================================
# El backend de persistencia vive en chat_history/postgres_store.py
crear_tabla_historial()

# ============================================
# 5. FUNCIÓN DE CHAT CON AGENTE + TOOLS
# ============================================
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
        return respuesta_bloqueada(motivo)
    # ───────────────────────────────────────────────────────────────

    # Combinar tools base con tools dinámicas del turno
    tools_turno = tools + (tools_extra or [])

    # Inyectar la fecha/hora actual en el system prompt de este turno
    system_content = (
        system_prompt
        + "\n\n---\nFECHA Y HORA ACTUAL (referencia para este turno): "
        + _contexto_fecha_hora()
    )

    # Agente LangChain v1: create_agent maneja el loop de tools internamente
    # y ejecuta el PIIMiddleware (Capa 5b) antes/después de llamar al modelo.
    # Se construye por turno para refrescar la fecha/hora y las tools dinámicas.
    agente = create_agent(
        model=chat,
        tools=tools_turno,
        system_prompt=system_content,
        middleware=crear_pii_middlewares(),
    )

    # Memoria: cargamos el historial de Postgres y lo pasamos como mensajes.
    # (Sin checkpointer, para conservar el backend actual de chat_history/.)
    history = get_session_history(session_id)
    input_messages = list(history.messages) + [HumanMessage(content=mensaje_usuario)]

    # create_agent devuelve el estado final; el último mensaje es la respuesta.
    resultado = agente.invoke({"messages": input_messages})
    respuesta_final = resultado["messages"][-1].content

    # Guardar en historial
    history.add_user_message(mensaje_usuario)
    history.add_ai_message(respuesta_final)

    return respuesta_final


# ============================================
# 6. LOOP DE CONVERSACIÓN
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
