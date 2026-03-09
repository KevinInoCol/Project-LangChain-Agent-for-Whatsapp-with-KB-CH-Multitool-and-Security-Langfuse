"""
HybridSafetyService — Capas 7 y 8 de Seguridad (IA via GROQ)

Combina dos modelos especializados de Meta:
  Capa 7 → Llama Prompt Guard 2 (86M params)
            Detecta Jailbreak / Prompt Injection
            Respuesta: "MALICIOUS" o "BENIGN"

  Capa 8 → Llama Guard 4 (12B params)
            Detecta NSFW, Hate, Violence, Self-Harm
            Respuesta: "safe" o "unsafe\nS1, S2, ..."

Estrategia:
  - Ejecuta Prompt Guard primero (rápido, enfocado en ataques)
  - Si pasa, ejecuta Llama Guard 4 (profundo, contenido NSFW)

Adaptación de async → sync respecto al código original del amigo,
porque el agente DataBot es síncrono (CLI script).

Requiere: pip install groq
          GROQ_API_KEY en el archivo .env

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


class HybridSafetyService:
    """
    Singleton service para verificaciones de seguridad IA usando Groq.

    Combina dos modelos especializados:
      1. Llama Prompt Guard 2 (86M) → Detecta Jailbreak/Prompt Injection
      2. Llama Guard 4 (12B)        → Detecta NSFW, Hate, Violence, Self-Harm

    Estrategia:
      - Ejecuta Prompt Guard primero (rápido, enfocado en ataques)
      - Si pasa y check_nsfw está activo, ejecuta Llama Guard 4
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Inicializa el cliente Groq (llamado una sola vez por el singleton)."""
        self.groq_client = None

        try:
            from groq import Groq
            self.groq_api_key = os.getenv("GROQ_API_KEY")

            if self.groq_api_key:
                self.groq_client = Groq(api_key=self.groq_api_key)
                logger.info("[SAFETY] ✅ Groq client inicializado")
            else:
                logger.warning("[SAFETY] ⚠️ GROQ_API_KEY no encontrada en el entorno")

        except ImportError:
            logger.error("[SAFETY] ❌ Groq SDK no instalado. Ejecuta: pip install groq")

        logger.info(f"[SAFETY] Servicio listo (Groq disponible: {bool(self.groq_client)})")

    def _call_model(self, model: str, message: str) -> str:
        """
        Llama al modelo en Groq de forma síncrona.
        (El código original del amigo usa asyncio.to_thread porque es un backend async.
         Aquí lo llamamos directo porque el agente DataBot es síncrono.)
        """
        chat_completion = self.groq_client.chat.completions.create(
            messages=[{"role": "user", "content": message}],
            model=model,
            temperature=0.0,
        )
        return chat_completion.choices[0].message.content.strip()

    # ----------------------------------------------------------
    # Capa 7: Llama Prompt Guard 2 — Jailbreak / Injection
    # ----------------------------------------------------------
    def validate_jailbreak(
        self,
        message: str,
        fail_close: bool = True,
    ) -> Tuple[bool, str]:
        """
        Verifica Jailbreak/Injection usando Llama Prompt Guard 2.

        Args:
            message:    Texto del usuario a verificar.
            fail_close: Si True, bloquea el mensaje cuando el servicio falla.
                        Si False, deja pasar (fail-open).

        Returns:
            (is_malicious, reason)
        """
        if not self.groq_client:
            return False, ""

        try:
            result = self._call_model("meta-llama/llama-prompt-guard-2-86m", message)

            if "MALICIOUS" in result.upper():
                logger.warning("[SAFETY] 🚨 Prompt Injection/Jailbreak detectado (Prompt Guard 2)")
                return True, "jailbreak_ia"

            return False, ""

        except Exception as e:
            if fail_close:
                logger.error(f"[SAFETY] ❌ Fail-Close activado en Jailbreak check: {e}")
                return True, "servicio_no_disponible"
            return False, ""

    # ----------------------------------------------------------
    # Capa 8: Llama Guard 4 — NSFW / Hate / Violence / Self-Harm
    # ----------------------------------------------------------
    def validate_toxicity(
        self,
        message: str,
        skip_categories: Optional[List[str]] = None,
        fail_close: bool = True,
    ) -> Tuple[bool, str]:
        """
        Verifica NSFW/Hate/Violence usando Llama Guard 4.

        Args:
            message:         Texto del usuario a verificar.
            skip_categories: Categorías de Llama Guard a ignorar.
                             Ejemplo: ['S7'] para ignorar privacidad.
            fail_close:      Si True, bloquea cuando el servicio falla.

        Returns:
            (is_unsafe, reason)

        Categorías de Llama Guard 4:
            S1  Violent Crimes
            S2  Non-Violent Crimes
            S3  Sex-Related Crimes
            S4  Child Sexual Exploitation
            S5  Defamation
            S6  Specialized Advice
            S7  Privacy
            S8  Intellectual Property
            S9  Indiscriminate Weapons
            S10 Hate
            S11 Suicide & Self-Harm
            S12 Sexual Content
            S13 Elections
        """
        if not self.groq_client:
            return False, ""

        skip_categories = skip_categories or []

        try:
            result = self._call_model("meta-llama/llama-guard-4-12b", message)

            if result.lower().startswith("unsafe"):
                raw_categories = result.replace("unsafe", "").strip().split(",")
                categories = [c.strip() for c in raw_categories if c.strip()]

                active_categories = [c for c in categories if c not in skip_categories]

                if active_categories:
                    logger.warning(
                        f"[SAFETY] 🚨 Contenido bloqueado: {active_categories} (Llama Guard 4)"
                    )
                    return True, "contenido_ia_bloqueado"
                else:
                    logger.info(f"[SAFETY] ⚠️ Categorías ignoradas: {categories} (config usuario)")
                    return False, ""

            return False, ""

        except Exception as e:
            if fail_close:
                logger.error(f"[SAFETY] ❌ Fail-Close activado en Toxicity check: {e}")
                return True, "servicio_no_disponible"
            return False, ""

    # ----------------------------------------------------------
    # Facade principal — ejecuta ambas capas en secuencia
    # ----------------------------------------------------------
    def validate_all(
        self,
        message: str,
        check_jailbreak: bool = True,
        check_nsfw: bool = True,
        skip_categories: Optional[List[str]] = None,
        fail_close: bool = True,
    ) -> Tuple[bool, str]:
        """
        Facade que ejecuta las validaciones secuencialmente.

        Args:
            check_jailbreak:  Activar Llama Prompt Guard 2.
            check_nsfw:       Activar Llama Guard 4.
            skip_categories:  Categorías de Llama Guard 4 a ignorar.
            fail_close:       Comportamiento ante fallos del servicio.

        Returns:
            (is_blocked, reason)
        """
        # Capa 7: Jailbreak (prioridad)
        if check_jailbreak:
            is_jailbreak, reason = self.validate_jailbreak(message, fail_close=fail_close)
            if is_jailbreak:
                return True, reason

        # Capa 8: Toxicidad (si pasó el jailbreak)
        if check_nsfw:
            is_toxic, reason = self.validate_toxicity(
                message,
                skip_categories=skip_categories,
                fail_close=fail_close,
            )
            if is_toxic:
                return True, reason

        return False, ""


# Alias para compatibilidad
LlamaGuardService = HybridSafetyService


def get_llama_guard_service() -> HybridSafetyService:
    """Retorna la instancia singleton de HybridSafetyService."""
    return HybridSafetyService()
