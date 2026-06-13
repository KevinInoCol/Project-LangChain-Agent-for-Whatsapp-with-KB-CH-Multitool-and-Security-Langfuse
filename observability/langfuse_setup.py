"""
Inicialización centralizada del cliente de Langfuse.

Langfuse() es un **singleton**: basta con invocarlo una vez al arrancar el
proceso. Cualquier módulo que luego haga `get_client()` recibe la misma
instancia, sin importar el orden de imports.

Centralizar la inicialización aquí tiene tres ventajas:
  1. Es obvio dónde se configura Langfuse (antes estaba mezclado con el
     código del agente).
  2. Cualquier módulo (agente, judge, scripts de evaluación...) puede
     hacer `from observability.langfuse_setup import langfuse_client`
     y evita dispersión de `get_client()` por el código.
  3. Si mañana cambias de proveedor de observabilidad (LangSmith, Helicone,
     OpenLLMetry...) solo tocas este archivo.

Lee LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY y LANGFUSE_BASE_URL del .env.
"""

import os

from langfuse import Langfuse, get_client

# Arranca el singleton (idempotente — llamarlo varias veces no rompe nada).
Langfuse()

# Instancia única que usan el agente, el judge y los scripts.
langfuse_client = get_client()

print(
    f"📊 Langfuse conectado: "
    f"{os.getenv('LANGFUSE_BASE_URL', 'https://cloud.langfuse.com')}"
)
