# 8 Capas de Seguridad

1. Secret Keys (REGEX)
- Detecta claves de API: sk-...., ghp_...., AIza...., gsk_....

2. Prompt Injection Patterns (REGEX)
- 60+ patrones ES/EN: "ignora instrucciones", "#SYSTEM", "modo desarrollador"....

3. Toxic Patterns (REGEX)
- Amenazas directas, hate speech, acoso sexual explícito, incitación a la violencia, autolesión

4. Custom Regex (REGEX)
- Patrones configurados por el admin (con protección ReDoS — Timeout 1s)

5. PII Detection (Presidio) (LOCAL)
- DNI, RUC, Email, Teléfono PE — Acciones: Mask / Block / off
- Presidio es una biblioteca open-source de Microsoft especializada en detectar y anonimizar datos personales sensibles (PII). Combina regex, NLP y Machine Learning para identificar información como DNI, email, teléfono, tarjeta de crédito y nombres de personas en cualquier texto.

6. Llama Prompt Guard 2 (GROQ API)
- Detección de Jailbreak/Injection mediante IA (86M params, 8 idiomas)

7. GPT-OSS-Safeguard (GROQ API)
- Clasificación NSFW / Violencia / Odio / Autolesión (20B params)
- Reemplaza a Llama Guard 4 (llama-guard-4-12b), deprecado en Groq el 2026-03-05

8. URL Filter (REGEX)
- Modos: off / whitelist / blacklist — Soporte a wildcards y dominios acortadores
