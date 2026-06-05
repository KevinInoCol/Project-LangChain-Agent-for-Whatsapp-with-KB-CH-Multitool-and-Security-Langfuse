"""
Backend de persistencia de conversación (Histórico) — PostgreSQL.

Guarda el histórico de cada sesión en una tabla de PostgreSQL usando
langchain_postgres.PostgresChatMessageHistory.

Esta carpeta es el ÚNICO lugar que conoce el backend de memoria. Cambiar de
Postgres a Redis/SQLite solo debería tocar este módulo (más otro
*_store.py) sin que el agente se entere.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
from urllib.parse import quote_plus

import psycopg
from dotenv import load_dotenv, find_dotenv
from langchain_postgres import PostgresChatMessageHistory

load_dotenv(find_dotenv())

# ============================================
# 1. CONFIGURACIÓN DE BASE DE DATOS
# ============================================
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

# Nombre de la tabla donde se almacena el histórico de conversaciones
TABLE_NAME = os.getenv("CHAT_HISTORY_TABLE", "chat_history")

if not all([DB_USER, DB_PASSWORD, DB_HOST]):
    raise ValueError(
        "❌ Faltan variables de base de datos en .env\n"
        "Requeridas: DB_USER, DB_PASSWORD, DB_HOST"
    )

DATABASE_URL = (
    f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

print(f"🔌 Conectando como: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


# ============================================
# 2. CREAR TABLA DE HISTORIAL
# ============================================
def crear_tabla_historial(table_name: str = TABLE_NAME) -> None:
    """Crea la tabla de histórico si no existe (idempotente)."""
    try:
        sync_connection = psycopg.connect(DATABASE_URL)
        PostgresChatMessageHistory.create_tables(sync_connection, table_name)
        sync_connection.close()
    except Exception as e:
        print(f"⚠️ Nota sobre tabla: {e}")


# ============================================
# 3. HISTÓRICO DE CONVERSACIÓN POR SESIÓN
# ============================================
def get_session_history(
    session_id: str,
    table_name: str = TABLE_NAME,
) -> PostgresChatMessageHistory:
    """Devuelve el historial persistente de una sesión (por UUID)."""
    sync_connection = psycopg.connect(DATABASE_URL)
    return PostgresChatMessageHistory(
        table_name,
        session_id,
        sync_connection=sync_connection,
    )
