"""
Middleware de PII (LangChain nativo) — material didáctico para el Programa AI Engineer.

Este módulo arma el `PIIMiddleware` nativo de LangChain v1 para que se pueda
enchufar a un agente creado con `create_agent(...)`.

¿Por qué un módulo aparte y no dentro del agente?
--------------------------------------------------
`PIIMiddleware` SOLO funciona con `create_agent` (la arquitectura de agente de
LangChain v1). El agente de producción de DataBot usa un loop manual
(`chat.bind_tools(...).invoke(...)`), donde el middleware NO se ejecuta. Por eso
esta pieza vive suelta y reutilizable en `guardrails/`, y se demuestra en
`demo_pii_middleware.py`.

Diferencia con la Capa 5 (guardrails/pii_detector.py)
-----------------------------------------------------
- Capa 5 (Presidio + spaCy): detección con NLP + score de confianza, pensada
  para BLOQUEAR PII peruano (DNI, RUC, teléfono PE) ANTES del agente.
- PIIMiddleware (este módulo): detección por REGEX/función, integrada en el
  ciclo del agente. Su valor añadido frente a la Capa 5:
    * Estrategias: además de `block`, puede `redact`, `mask` y `hash`
      (sanea y deja continuar la conversación, mejor UX que rechazar).
    * Cobertura: puede revisar también la SALIDA del modelo y los resultados
      de las tools (apply_to_output / apply_to_tool_results), no solo el input.

Tipos PII integrados en LangChain: email, credit_card (Luhn), ip, mac_address, url.
Todo lo demás (DNI/RUC/teléfono PE) se agrega con `detector` personalizado.

Estrategias disponibles:
    block  → lanza excepción cuando detecta
    redact → reemplaza por [REDACTED_{TIPO}]
    mask   → enmascara parcialmente (ej. ****-****-****-1234)
    hash   → reemplaza por un hash determinista

Requiere: langchain>=1.0.0

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import re
from typing import Dict, List, Union

from langchain.agents.middleware import PIIMiddleware


# ============================================================
# DETECTORES PERSONALIZADOS (PII peruano)
# ------------------------------------------------------------
# Un detector custom recibe el texto y devuelve una lista de dicts con las
# claves exactas: {"text", "start", "end"}. Así el middleware sabe QUÉ y DÓNDE
# aplicar la estrategia (redact/mask/hash/block).
# ============================================================

# Reutilizamos los mismos patrones que la Capa 5 para mantener coherencia.
_DNI_PE_RE = re.compile(r"\b\d{8}\b")
_RUC_PE_RE = re.compile(r"\b(?:10|15|17|20)\d{9}\b")
_PHONE_PE_RE = re.compile(r"(?:\+51|51)?\s*9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b")


def _matches(patron: re.Pattern, contenido: str) -> List[Dict[str, Union[str, int]]]:
    """Convierte los matches de un regex al formato que espera PIIMiddleware."""
    return [
        {"text": m.group(0), "start": m.start(), "end": m.end()}
        for m in patron.finditer(contenido)
    ]


def detectar_dni_pe(contenido: str) -> List[Dict[str, Union[str, int]]]:
    """DNI peruano: 8 dígitos. (Ojo: regex puro → propenso a falsos positivos.)"""
    return _matches(_DNI_PE_RE, contenido)


def detectar_ruc_pe(contenido: str) -> List[Dict[str, Union[str, int]]]:
    """RUC peruano: 11 dígitos que empiezan en 10/15/17/20."""
    return _matches(_RUC_PE_RE, contenido)


def detectar_telefono_pe(contenido: str) -> List[Dict[str, Union[str, int]]]:
    """Teléfono móvil peruano: 9XXXXXXXX, con +51 opcional."""
    return _matches(_PHONE_PE_RE, contenido)


# ============================================================
# FACTORY — lista de middlewares lista para create_agent(...)
# ============================================================
def crear_pii_middlewares(
    aplicar_a_salida: bool = False,
    aplicar_a_tools: bool = False,
) -> List[PIIMiddleware]:
    """
    Devuelve la lista de PIIMiddleware configurada para DataBot.

    Cada middleware maneja UN tipo de PII. El orden importa poco (se aplican
    todos), pero conviene poner los `block` primero por claridad.

    Args:
        aplicar_a_salida: si True, también revisa/sanea la respuesta del modelo.
        aplicar_a_tools:  si True, también revisa/sanea los resultados de tools
                          (útil si tu RAG/Pinecone pudiera devolver PII).

    Returns:
        Lista de PIIMiddleware para pasar a create_agent(middleware=...).

    Demostración de las 4 estrategias:
        - api_key      → block  (corta la ejecución: dato crítico)
        - email        → redact ([REDACTED_EMAIL])
        - dni / ruc    → redact (identificadores peruanos)
        - credit_card  → mask   (****-****-****-1234)
        - phone_pe     → mask
        - ip           → hash   (hash determinista)
    """
    comun = {
        "apply_to_input": True,
        "apply_to_output": aplicar_a_salida,
        "apply_to_tool_results": aplicar_a_tools,
    }

    return [
        # ── block: dato crítico, mejor cortar ──────────────────────────
        PIIMiddleware(
            "api_key",
            detector=r"sk-[a-zA-Z0-9]{20,}",
            strategy="block",
            **comun,
        ),
        # ── redact: reemplazo por etiqueta ─────────────────────────────
        PIIMiddleware("email", strategy="redact", **comun),  # tipo integrado
        PIIMiddleware("dni_pe", detector=detectar_dni_pe, strategy="redact", **comun),
        PIIMiddleware("ruc_pe", detector=detectar_ruc_pe, strategy="redact", **comun),
        # ── mask: enmascarado parcial ──────────────────────────────────
        PIIMiddleware("credit_card", strategy="mask", **comun),  # tipo integrado (Luhn)
        PIIMiddleware("phone_pe", detector=detectar_telefono_pe, strategy="mask", **comun),
        # ── hash: seudonimización determinista ─────────────────────────
        PIIMiddleware("ip", strategy="hash", **comun),  # tipo integrado
    ]
