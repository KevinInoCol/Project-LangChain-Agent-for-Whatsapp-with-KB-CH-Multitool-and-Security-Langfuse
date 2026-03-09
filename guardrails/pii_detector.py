"""
PiiDetector — Capa 5 de Seguridad: Detección de Datos Personales Sensibles (PII)

Detecta información personal en mensajes de usuarios para Perú y LATAM.

Entidades detectadas:
  - DNI         → Documento Nacional de Identidad (8 dígitos)
  - RUC         → Registro Único de Contribuyentes (11 dígitos)
  - Email       → Correo electrónico
  - Teléfono    → Formato peruano (+51 / 9XXXXXXXX)
  - Tarjeta     → Números de tarjeta de crédito/débito (13-19 dígitos)

Acción configurable por entidad:
  - "block"  → Bloquea el mensaje completo
  - "mask"   → Enmascara el dato y permite pasar el mensaje (futuro)
  - "off"    → Desactiva la detección de esa entidad

Requiere: presidio-analyzer, presidio-anonymizer (opcional, ver requirements.txt)
Si Presidio no está instalado, funciona con detección pura por regex.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURACIÓN DE ENTIDADES PII
# Cambiar acción por entidad según necesidad del proyecto
# ============================================================
PII_CONFIG: Dict[str, str] = {
    "DNI_PE":       "block",   # DNI peruano — 8 dígitos
    "RUC_PE":       "block",   # RUC — 11 dígitos (10/15/17/20 + 9 dígitos)
    "EMAIL":        "block",   # Correo electrónico
    "PHONE_PE":     "block",   # Teléfono peruano
    "CREDIT_CARD":  "block",   # Tarjeta de crédito/débito
}


# ============================================================
# PATRONES REGEX POR ENTIDAD
# ============================================================
_PII_PATTERNS = {
    "DNI_PE": re.compile(
        r"\b\d{8}\b"
    ),
    "RUC_PE": re.compile(
        r"\b(10|15|17|20)\d{9}\b"
    ),
    "EMAIL": re.compile(
        r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
    ),
    "PHONE_PE": re.compile(
        r"(\+51|51)?\s*9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b"
    ),
    "CREDIT_CARD": re.compile(
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"       # Visa
        r"5[1-5][0-9]{14}|"                     # MasterCard
        r"3[47][0-9]{13}|"                      # Amex
        r"6(?:011|5[0-9]{2})[0-9]{12})\b"       # Discover
    ),
}


class PiiDetector:
    """
    Detecta datos personales sensibles (PII) en mensajes.

    Intenta usar Presidio (Microsoft) si está instalado.
    Si no está instalado, usa detección por regex puro.
    """

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or PII_CONFIG
        self._presidio_analyzer = None
        self._init_presidio()

    def _init_presidio(self) -> None:
        """Intenta inicializar Presidio con reconocedores personalizados para Perú."""
        try:
            from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            # Configuración sin modelo spacy pesado (usa NLP mínimo)
            provider = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "es", "model_name": "es_core_news_sm"}],
            })
            nlp_engine = provider.create_engine()

            analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["es", "en"])

            # Reconocedor: DNI Perú
            analyzer.registry.add_recognizer(PatternRecognizer(
                supported_entity="DNI_PE",
                patterns=[Pattern("DNI_PE", r"\b\d{8}\b", 0.7)],
                supported_language="es",
            ))

            # Reconocedor: RUC Perú
            analyzer.registry.add_recognizer(PatternRecognizer(
                supported_entity="RUC_PE",
                patterns=[Pattern("RUC_PE", r"\b(10|15|17|20)\d{9}\b", 0.85)],
                supported_language="es",
            ))

            # Reconocedor: Teléfono Perú
            analyzer.registry.add_recognizer(PatternRecognizer(
                supported_entity="PHONE_PE",
                patterns=[Pattern("PHONE_PE", r"(\+51|51)?\s*9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b", 0.75)],
                supported_language="es",
            ))

            self._presidio_analyzer = analyzer
            logger.info("[PII] Presidio inicializado con reconocedores para Perú (ES)")

        except ImportError:
            logger.info("[PII] Presidio no instalado — usando detección por regex puro")
        except Exception as e:
            logger.warning(f"[PII] Presidio no disponible ({e}) — usando regex puro")

    def detectar(self, texto: str) -> List[str]:
        """
        Analiza el texto y retorna lista de entidades PII detectadas
        cuya acción es 'block'.

        Returns:
            Lista de strings con los tipos detectados, ej: ["DNI_PE", "EMAIL"]
            Lista vacía si el mensaje es seguro.
        """
        if not texto or not texto.strip():
            return []

        activas = [k for k, v in self.config.items() if v == "block"]
        detectadas: List[str] = []

        if self._presidio_analyzer:
            detectadas = self._detectar_con_presidio(texto, activas)
        else:
            detectadas = self._detectar_con_regex(texto, activas)

        return detectadas

    def _detectar_con_presidio(self, texto: str, entidades: List[str]) -> List[str]:
        """Usa Presidio para detectar PII con NLP + regex."""
        try:
            resultados = self._presidio_analyzer.analyze(
                text=texto,
                language="es",
                entities=entidades,
            )
            detectadas = list({r.entity_type for r in resultados if r.score >= 0.6})
            if detectadas:
                logger.warning(f"[PII Presidio] Detectado: {detectadas}")
            return detectadas
        except Exception as e:
            logger.error(f"[PII Presidio] Error en análisis: {e}")
            return self._detectar_con_regex(texto, entidades)

    def _detectar_con_regex(self, texto: str, entidades: List[str]) -> List[str]:
        """Fallback: detección pura por regex."""
        detectadas = []
        for entidad in entidades:
            pattern = _PII_PATTERNS.get(entidad)
            if pattern and pattern.search(texto):
                logger.warning(f"[PII Regex] {entidad} detectado en: {texto[:60]!r}")
                detectadas.append(entidad)
        return detectadas
