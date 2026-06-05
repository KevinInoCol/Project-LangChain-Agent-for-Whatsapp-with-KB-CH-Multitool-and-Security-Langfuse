"""
Módulo de Histórico de Conversación (chat_history).

Backend de persistencia de conversaciones intercambiable. Actualmente: PostgreSQL.
El agente consume solo esta API pública y no sabe qué backend hay debajo.
"""

from chat_history.postgres_store import (
    DATABASE_URL,
    TABLE_NAME,
    crear_tabla_historial,
    get_session_history,
)

__all__ = [
    "DATABASE_URL",
    "TABLE_NAME",
    "crear_tabla_historial",
    "get_session_history",
]
