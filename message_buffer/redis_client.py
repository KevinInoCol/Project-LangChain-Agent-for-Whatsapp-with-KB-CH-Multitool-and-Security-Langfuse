"""
Cliente Redis (asíncrono) para el buffer de mensajes.

Construye una única conexión a Redis a partir del .env:
  - Opción A: REDIS_URL  (un solo string; usa rediss:// para TLS)
  - Opción B: REDIS_HOST + REDIS_PORT + REDIS_DB + REDIS_PASSWORD (+ REDIS_TLS)

La conexión se crea de forma perezosa la primera vez que se usa, ya dentro
del event loop de FastAPI/uvicorn.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import logging

import redis.asyncio as redis
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

logger = logging.getLogger(__name__)

_client: "redis.Redis | None" = None


def _to_bool(valor: str) -> bool:
    return str(valor).strip().lower() in ("1", "true", "yes", "on", "si", "sí")


def get_redis() -> "redis.Redis":
    """Devuelve el cliente Redis singleton (lo crea en la primera llamada)."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("REDIS_URL", "").strip()

    if url:
        # Opción A: URL única (rediss:// activa TLS automáticamente)
        _client = redis.from_url(url, decode_responses=True)
        logger.info("[REDIS] Cliente creado desde REDIS_URL")
    else:
        # Opción B: variables granulares
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD") or None
        use_tls = _to_bool(os.getenv("REDIS_TLS", "false"))

        _client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=use_tls,
            decode_responses=True,
        )
        logger.info(f"[REDIS] Cliente creado: {host}:{port}/{db} (TLS={use_tls})")

    return _client
