"""
Configuración del buffer de mensajes (debounce de WhatsApp/Chatwoot).

Lee del .env las variables MESSAGE_BUFFER_* que controlan cómo se acumulan
y concatenan los mensajes entrantes antes de pasarlos al agente.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def _to_bool(valor: str) -> bool:
    return str(valor).strip().lower() in ("1", "true", "yes", "on", "si", "sí")


# ¿Buffer activo? Si es False, el agente responde mensaje por mensaje (modo antiguo).
ENABLED = _to_bool(os.getenv("MESSAGE_BUFFER_ENABLED", "true"))

# Ventana de espera sin nuevos mensajes antes de concatenar y disparar la respuesta.
WINDOW_SECONDS = float(os.getenv("MESSAGE_BUFFER_WINDOW_SECONDS", "15"))

# TTL de las claves del buffer en Redis (evita fugas si una conversación queda a medias).
TTL_SECONDS = int(os.getenv("MESSAGE_BUFFER_TTL_SECONDS", "300"))

# Separador al concatenar los mensajes acumulados.
# En el .env "\n" llega como texto literal (barra + n); lo convertimos al salto real.
_raw_sep = os.getenv("MESSAGE_BUFFER_SEPARATOR", "\n")
SEPARATOR = _raw_sep.encode().decode("unicode_escape")
