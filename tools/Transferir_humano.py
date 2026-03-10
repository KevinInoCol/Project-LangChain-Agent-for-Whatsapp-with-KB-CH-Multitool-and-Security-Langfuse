"""
Tool: Transferir a Humano (Handoff IA → Asesor)
Coloca el tag "ia-off" en el CONTACTO y en la CONVERSACIÓN de Chatwoot
para desactivar el bot de forma inmediata y permanente.

APIs usadas:
  - Contacto:     POST /api/v1/accounts/{account_id}/contacts/{id}/labels
    https://developers.chatwoot.com/api-reference/contact-labels/add-labels
  - Conversación: POST /api/v1/accounts/{account_id}/conversations/{id}/labels
    (para que el webhook detecte "ia-off" en el payload de inmediato)

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import requests
from typing import Callable

from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool

load_dotenv(find_dotenv())

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "").rstrip("/")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID")
CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_ACCESS_TOKEN")

TAG_IA_OFF = "ia-off"

_HEADERS = lambda: {  # noqa: E731
    "api_access_token": CHATWOOT_API_TOKEN,
    "Content-Type": "application/json",
}


# ============================================================
# FUNCIONES INTERNAS
# ============================================================
def _agregar_label_contacto(contact_id: int) -> list[str]:
    """
    Agrega "ia-off" al CONTACTO.
    POST /api/v1/accounts/{account_id}/contacts/{id}/labels

    La API sobreescribe todos los labels, así que primero hace GET
    para obtener los existentes y luego los fusiona antes del POST.
    """
    base = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/{contact_id}"

    try:
        get_resp = requests.get(f"{base}/labels", headers=_HEADERS(), timeout=10)
        get_resp.raise_for_status()
        labels_actuales: list[str] = get_resp.json().get("payload", [])
    except Exception:
        labels_actuales = []

    if TAG_IA_OFF not in labels_actuales:
        labels_actuales.append(TAG_IA_OFF)

    post_resp = requests.post(
        f"{base}/labels",
        json={"labels": labels_actuales},
        headers=_HEADERS(),
        timeout=10,
    )
    post_resp.raise_for_status()
    return post_resp.json().get("payload", labels_actuales)


def _agregar_label_conversacion(conversation_id: int) -> list[str]:
    """
    Agrega "ia-off" a la CONVERSACIÓN.
    POST /api/v1/accounts/{account_id}/conversations/{id}/labels

    Esto es necesario para que el check del webhook (conversation.labels)
    detecte "ia-off" a partir del próximo mensaje entrante.
    """
    base = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}"

    try:
        get_resp = requests.get(f"{base}/labels", headers=_HEADERS(), timeout=10)
        get_resp.raise_for_status()
        labels_actuales: list[str] = get_resp.json().get("payload", [])
    except Exception:
        labels_actuales = []

    if TAG_IA_OFF not in labels_actuales:
        labels_actuales.append(TAG_IA_OFF)

    post_resp = requests.post(
        f"{base}/labels",
        json={"labels": labels_actuales},
        headers=_HEADERS(),
        timeout=10,
    )
    post_resp.raise_for_status()
    return post_resp.json().get("payload", labels_actuales)


# ============================================================
# FACTORY: crea la tool con contact_id y conversation_id inyectados
# ============================================================
def crear_tool_transferir_humano(contact_id: int, conversation_id: int) -> Callable:
    """
    Crea y devuelve una LangChain tool con contact_id y conversation_id
    pre-inyectados como closure.

    Etiqueta AMBOS recursos con "ia-off":
      1. Contacto     → desactivación permanente (todas sus conversaciones futuras)
      2. Conversación → desactivación inmediata en el webhook actual

    Args:
        contact_id:      ID del contacto (sender.id del webhook).
        conversation_id: ID de la conversación (conversation.id del webhook).

    Returns:
        LangChain tool lista para añadir al agente.

    Ejemplo:
        tool_handoff = crear_tool_transferir_humano(contact_id=2, conversation_id=5)
        respuesta = chat_con_agente(mensaje, session_id, tools_extra=[tool_handoff])
    """

    @tool
    def transferir_a_humano() -> str:
        """
        Transfiere la conversación a un asesor humano y desactiva la IA.

        Usa esta herramienta ÚNICAMENTE cuando el usuario exprese claramente
        que quiere comunicarse con una persona real, por ejemplo:
        - "quiero hablar con un humano / una persona / un asesor"
        - "necesito soporte personalizado"
        - "comunícame con alguien"
        - "prefiero atención humana"
        - "pásame con un representante"

        Tras ejecutar esta herramienta el agente IA dejará de responder
        tanto en esta conversación como en futuras del mismo contacto.
        """
        print(
            f"   🤝 [HANDOFF] Aplicando '{TAG_IA_OFF}' → "
            f"contacto {contact_id} | conversación {conversation_id}..."
        )

        if not all([CHATWOOT_BASE_URL, CHATWOOT_ACCOUNT_ID, CHATWOOT_API_TOKEN]):
            print("   ⚠️  [HANDOFF] Configuración de Chatwoot incompleta.")
            return (
                "Entendido. He notificado al equipo y un asesor se pondrá en contacto "
                "contigo en breve. Por favor aguarda unos minutos. ¡Gracias por tu paciencia!"
            )

        errores = []

        # 1. Etiquetar el contacto (desactivación permanente)
        try:
            labels_contacto = _agregar_label_contacto(contact_id)
            print(f"   ✅ [HANDOFF] Contacto {contact_id} etiquetado: {labels_contacto}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ [HANDOFF] Error al etiquetar contacto: {e}")
            errores.append("contacto")

        # 2. Etiquetar la conversación (desactivación inmediata en webhook)
        try:
            labels_conv = _agregar_label_conversacion(conversation_id)
            print(f"   ✅ [HANDOFF] Conversación {conversation_id} etiquetada: {labels_conv}")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ [HANDOFF] Error al etiquetar conversación: {e}")
            errores.append("conversación")

        if errores:
            print(f"   ⚠️  [HANDOFF] Falló el etiquetado en: {errores}")

        return (
            "Perfecto, he notificado a nuestro equipo. Un asesor humano tomará "
            "tu conversación en breve — por favor aguarda unos minutos. "
            "¡Gracias por tu paciencia!"
        )

    return transferir_a_humano
