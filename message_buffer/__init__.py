"""
Módulo de Buffer de Mensajes (message_buffer).

Acumula los mensajes que el usuario envía seguidos y los concatena en una
sola entrada para el agente, evitando respuestas duplicadas. El backend de
almacenamiento temporal es Redis.

API pública:
    from message_buffer import encolar_mensaje, BUFFER_ENABLED
"""

from message_buffer.buffer import encolar_mensaje
from message_buffer.config import (
    ENABLED as BUFFER_ENABLED,
    WINDOW_SECONDS as BUFFER_WINDOW_SECONDS,
)

__all__ = [
    "encolar_mensaje",
    "BUFFER_ENABLED",
    "BUFFER_WINDOW_SECONDS",
]
