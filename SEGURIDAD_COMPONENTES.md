# Componentes de Seguridad del Proyecto DataBot

**Autor:** Ing. Kevin Inofuente Colque — DataPath  
**Proyecto:** Agente IA Multi-Tool con Seguridad para WhatsApp / Chatwoot  
**Módulo:** 1 — Sesión 1 — Programa AI Engineer

---

## ¿Qué es el InputGuardrail?

El **InputGuardrail** es el sistema de seguridad del proyecto. Es un pipeline de validación que intercepta **cada mensaje del usuario** antes de que llegue al agente de inteligencia artificial (GPT-4.1).

Su función es actuar como un portero inteligente: analiza el contenido del mensaje en múltiples dimensiones y decide si es seguro enviarlo al agente o si debe ser bloqueado con un mensaje de respuesta apropiado.

### ¿Por qué es necesario?

Los agentes de IA basados en modelos de lenguaje (LLMs) son vulnerables a distintos tipos de ataques:

- **Prompt Injection:** el usuario manipula el sistema con instrucciones disfrazadas de preguntas
- **Jailbreak:** el usuario intenta eliminar las restricciones del agente
- **Extracción de información sensible:** el usuario intenta revelar la arquitectura, claves o datos del sistema
- **Contenido dañino:** amenazas, discurso de odio, contenido sexual, autolesión
- **Exposición de datos personales:** usuarios que comparten DNI, RUC, teléfono sin darse cuenta

El InputGuardrail protege contra todos estos vectores de ataque.

---

## Arquitectura del Pipeline

Cada mensaje pasa por 8 capas en orden. Si cualquier capa detecta un problema, el mensaje es bloqueado de inmediato y no llega al agente.

```
Mensaje del usuario
        │
        ▼
┌───────────────────────────────────────────────────┐
│  CAPA 1 — Secret Keys (REGEX)                     │
│  CAPA 2 — Prompt Injection (REGEX)                │
│  CAPA 3 — Toxic Patterns (REGEX)                  │
│  CAPA 4 — Custom Regex (ReDoS-safe)               │
│  CAPA 5 — PII Detection / Presidio (LOCAL)        │
│  CAPA 7 — Llama Prompt Guard 2 (GROQ / META IA)  │
│  CAPA 8 — Llama Guard 4 (GROQ / META IA)         │
│  CAPA 6 — URL Filter (REGEX)                      │
└───────────────────────────────────────────────────┘
        │ (solo si pasa todas las capas)
        ▼
   Agente IA — GPT-4.1
```

> Las capas se ejecutan en ese orden exacto. Las capas REGEX van primero porque son instantáneas. Las capas de IA (7 y 8) van al final porque hacen llamadas externas a la API de Groq.

---

## Capa 1 — Detección de Claves Secretas (Secret Keys)

**Tecnología:** Expresiones Regulares (REGEX)  
**Velocidad:** Instantánea  

### ¿Qué detecta?

Detecta si el usuario ha incluido accidentalmente (o intencionalmente) una clave de API, token de acceso u otra credencial secreta en su mensaje.

### ¿Por qué es importante?

Si un usuario envía su propia API key de OpenAI o GitHub en un mensaje, ese dato quedaría registrado en los logs del sistema, en el historial de la base de datos PostgreSQL y potencialmente en los registros de la API de OpenAI. Esta capa previene esa filtración.

### Ejemplos de lo que bloquea

| Formato | Ejemplo | Servicio |
|---|---|---|
| `sk-...` | `sk-abc123xyz789...` | OpenAI |
| `sk-proj-...` | `sk-proj-xxxx...` | OpenAI Projects |
| `sk-ant-...` | `sk-ant-xxxx...` | Anthropic (Claude) |
| `ghp_...` | `ghp_xxxx...` | GitHub Personal Token |
| `AIza...` | `AIzaSyXXXX...` | Google API |
| `gsk_...` | `gsk_xxxx...` | Groq |
| `AKIA...` | `AKIAXXXXXXXX...` | AWS Access Key |
| `tvly-...` | `tvly-xxxx...` | Tavily |
| `eyJ...` | `eyJhbGci...` | JWT Token |
| `Bearer ...` | `Bearer xxxxx...` | Auth Token genérico |

### Mensaje de respuesta al usuario

> *"Lo siento, tu mensaje parece contener una clave de API o token secreto. Por seguridad, nunca compartas credenciales en el chat. Por favor, elimina cualquier clave o token y vuelve a escribir tu consulta."*

---

## Capa 2 — Detección de Prompt Injection

**Tecnología:** Expresiones Regulares (REGEX) — más de 60 patrones en Español e Inglés  
**Velocidad:** Instantánea  

### ¿Qué detecta?

Detecta intentos del usuario de manipular, hackear o subvertir el comportamiento del agente mediante instrucciones disfrazadas dentro de un mensaje.

### Categorías de ataque que cubre

**1. Sobrescritura del System Message**
El usuario intenta inyectar instrucciones de sistema directamente.  
Ejemplos: `#SYSTEM`, `[SYSTEM]`, `<system>`, `<<SYS>>`, `[INST]`

**2. Instrucciones de Ignorar (EN + ES)**
El usuario pide al agente que ignore sus instrucciones originales.  
Ejemplos: *"ignore all previous instructions"*, *"ignora todas las instrucciones"*, *"olvida tus reglas"*

**3. Ataques de Roleplay**
El usuario intenta que el agente adopte otro rol o identidad.  
Ejemplos: *"you are now a..."*, *"pretend to be..."*, *"ahora eres un..."*, *"actúa como si fueras..."*

**4. Frases de Jailbreak**
El usuario intenta desactivar las restricciones del agente.  
Ejemplos: *"DAN mode"*, *"Developer Mode"*, *"jailbreak"*, *"sin restricciones"*, *"modo desarrollador"*, *"versión sin filtro"*

**5. Extracción del Prompt**
El usuario intenta que el agente revele sus instrucciones internas.  
Ejemplos: *"reveal your system prompt"*, *"muéstrame tus instrucciones"*, *"cuáles son tus instrucciones"*

**6. Comandos de Debug/Admin**
El usuario intenta comandos de acceso privilegiado.  
Ejemplos: `/debug`, `/admin`, `/sudo`, `/root`, `[DEBUG]`, `[ADMIN]`

**7. Reconocimiento de Infraestructura**
El usuario intenta descubrir la tecnología, base de datos o arquitectura del sistema.  
Ejemplos: *"qué base de datos usas"*, *"usas Pinecone"*, *"cuéntame tu arquitectura"*, *"en qué servidor corres"*

**8. Ingeniería Inversa del Código**
El usuario intenta obtener el código fuente del agente.  
Ejemplos: *"dame el código para construirte"*, *"muéstrame el código de este bot"*

### Mensaje de respuesta al usuario

> *"Lo siento, no puedo procesar ese mensaje. Por favor, reformula tu pregunta de manera apropiada."*
>
> Para reconocimiento de infraestructura: *"Lo siento, no puedo compartir información sobre la arquitectura, tecnologías o configuración interna del sistema."*

---

## Capa 3 — Detección de Contenido Tóxico

**Tecnología:** Expresiones Regulares (REGEX) — patrones en Español e Inglés  
**Velocidad:** Instantánea  

### ¿Qué detecta?

Detecta mensajes que contienen lenguaje dañino, agresivo o inapropiado que no debería procesarse en ningún contexto.

### Categorías de toxicidad que cubre

**1. Amenazas Directas (EN + ES)**  
Mensajes que expresan intención de daño físico hacia otra persona.  
Ejemplos: *"te voy a matar"*, *"i will kill you"*, *"te voy a encontrar"*, *"sé dónde vives"*

**2. Discurso de Odio / Hate Speech (EN + ES)**  
Lenguaje que discrimina o ataca grupos por su origen, raza o religión.  
Ejemplos: frases con discriminación racial, étnica o religiosa, términos de odio.

**3. Acoso Sexual (EN + ES)**  
Mensajes con contenido sexual explícito no deseado o solicitudes de material íntimo.

**4. Incitación a la Violencia (EN + ES)**  
Mensajes que incitan a atacar a personas o grupos, o solicitan información para fabricar armas.  
Ejemplos: *"cómo hacer una bomba"*, *"bomba casera"*, *"instrucciones para matar"*

**5. Autolesión / Self-Harm (EN + ES)**  
Mensajes que incitan al daño propio o al suicidio.  
Ejemplos: *"mátate"*, *"suicídate"*, *"kill yourself"*, *"end your life"*

### Mensaje de respuesta al usuario

> *"Lo siento, no puedo continuar con esa conversación. Tu mensaje contiene contenido inapropiado. Por favor, mantén un trato respetuoso."*

---

## Capa 4 — Patrones Personalizados (Custom Regex)

**Tecnología:** Expresiones Regulares con protección anti-ReDoS  
**Velocidad:** Instantánea (con timeout de 1 segundo por patrón)  

### ¿Qué es?

Es una capa de configuración libre que permite al administrador del proyecto agregar sus propios patrones de bloqueo sin modificar el código principal. Se edita directamente en `input_guardrail.py`.

### Protección anti-ReDoS

Un ataque **ReDoS (Regular Expression Denial of Service)** ocurre cuando una expresión regular mal diseñada tarda exponencialmente más tiempo en procesar ciertos inputs, bloqueando el servidor. Esta capa ejecuta cada regex con un **timeout de 1 segundo**: si el patrón tarda más de ese tiempo, se ignora y no bloquea el sistema.

### Casos de uso típicos

- Bloquear menciones de competidores por nombre
- Bloquear frases como "precio gratis" o "descuento total"
- Bloquear palabras clave específicas del negocio que no deben tratarse en el chat

---

## Capa 5 — Detección de Datos Personales (PII)

**Tecnología:** Microsoft Presidio + Regex de respaldo  
**Velocidad:** Rápida (procesamiento local, sin APIs externas)  

### ¿Qué es Presidio?

**Presidio** es una librería open-source de **Microsoft** especializada en detectar y anonimizar datos personales sensibles (PII — Personally Identifiable Information). Combina **expresiones regulares**, **NLP (Procesamiento de Lenguaje Natural)** y **Machine Learning** para identificar información personal en cualquier texto.

### ¿Qué detecta?

La detección está configurada específicamente para **Perú y LATAM**:

| Entidad | Descripción | Ejemplo |
|---|---|---|
| `DNI_PE` | Documento Nacional de Identidad (8 dígitos exactos) | `12345678` |
| `RUC_PE` | Registro Único de Contribuyentes (11 dígitos, empieza en 10/15/17/20) | `20123456789` |
| `EMAIL` | Correo electrónico en cualquier formato | `usuario@correo.com` |
| `PHONE_PE` | Teléfono peruano (+51 o 9XXXXXXXX) | `+51 987 654 321` |
| `CREDIT_CARD` | Tarjetas Visa, MasterCard, Amex, Discover | `4111 1111 1111 1111` |

### Acciones configurables por entidad

Cada entidad puede configurarse con una de tres acciones:
- **`block`** — Bloquea el mensaje completo (configuración actual para todas las entidades)
- **`mask`** — Enmascara el dato y permite pasar el mensaje (disponible para implementar)
- **`off`** — Desactiva la detección de esa entidad

### Modo de operación dual

La capa funciona en dos modos automáticamente:
1. **Con Presidio instalado:** usa NLP + regex con scores de confianza (mínimo 0.6 para bloquear)
2. **Sin Presidio instalado:** usa detección por regex puro como fallback, sin interrumpir el servicio

### Mensaje de respuesta al usuario

> *"Lo siento, tu mensaje contiene información personal sensible (DNI, RUC, teléfono, etc.). Por seguridad, no compartas datos personales en el chat."*

---

## Capa 6 — Filtro de URLs

**Tecnología:** Expresiones Regulares (REGEX)  
**Velocidad:** Moderada (ejecutada al final por ser ligeramente más costosa)  

### ¿Qué detecta?

Detecta cualquier enlace o URL dentro del mensaje del usuario, incluyendo:

- URLs con protocolo: `https://...`, `http://...`, `ftp://...`
- URLs sin protocolo: `dominio.com`, `sitio.pe`, `app.io`
- Dominios acortadores de URL (blacklist): `bit.ly`, `tinyurl.com`, `t.co`, `goo.gl`, y más de 20 acortadores conocidos

### ¿Por qué bloquear URLs?

- Previene ataques de **phishing** donde el usuario intenta que el agente visite o procese un link malicioso
- Evita que el agente sea usado como intermediario para redirigir a sitios externos
- Protege contra técnicas de **prompt injection indirecto** donde el contenido dañino está en una URL

### Soporte de TLDs

Reconoce más de 60 extensiones de dominio (TLDs), incluyendo dominios específicos de Latinoamérica: `.pe`, `.mx`, `.ar`, `.co`, `.cl`, `.com.pe`, `.gob.pe`, `.edu.pe`, entre otros.

### Mensaje de respuesta al usuario

> *"Lo siento, no puedo procesar mensajes que contengan enlaces o URLs. Por favor, escribe tu pregunta en texto sin incluir links."*

---

## Capa 7 — Llama Prompt Guard 2 (IA de Meta via Groq)

**Tecnología:** Modelo de IA de Meta ejecutado en la infraestructura de Groq  
**Modelo:** `meta-llama/llama-prompt-guard-2-86m`  
**Tamaño:** 86 millones de parámetros  
**Velocidad:** Rápida (modelo pequeño, optimizado para clasificación binaria)  

### ¿Qué es?

**Llama Prompt Guard 2** es un modelo de inteligencia artificial desarrollado por **Meta** (la empresa detrás de Facebook e Instagram) específicamente para detectar ataques de **prompt injection y jailbreak** en sistemas de IA. Fue entrenado con miles de ejemplos reales de intentos de manipulación.

### ¿Qué detecta?

Su única función es determinar si un mensaje es un intento de manipular o hackear un sistema de IA. No analiza el contenido en general, solo busca patrones de ataque que los sistemas de REGEX pueden no capturar (ataques redactados creativamente, en otros idiomas, con errores ortográficos intencionales, etc.).

### ¿Cómo funciona?

1. El mensaje del usuario se envía a la **API de Groq** (servicio de inferencia de IA)
2. Groq ejecuta el modelo `llama-prompt-guard-2-86m` sobre el mensaje
3. El modelo devuelve una sola palabra: `MALICIOUS` o `BENIGN`
4. Si es `MALICIOUS`, el mensaje se bloquea

### Configuración técnica

- **Temperature: 0.0** — sin aleatoriedad, respuesta 100% determinista (lo correcto para un clasificador de seguridad)
- **Fail-close:** si la API de Groq no responde o falla, el mensaje se bloquea por precaución
- Soporta **8 idiomas** incluyendo español e inglés

### ¿Por qué Groq y no OpenAI?

Groq tiene una arquitectura de hardware especializada (LPU — Language Processing Unit) que permite inferencia de modelos de IA a velocidades extremadamente altas. Para una capa de seguridad que debe ser rápida, Groq es la elección óptima.

### Mensaje de respuesta al usuario

> *"Lo siento, no puedo procesar ese mensaje. Por favor, reformula tu pregunta de manera apropiada."*

---

## Capa 8 — Llama Guard 4 (IA de Meta via Groq)

**Tecnología:** Modelo de IA de Meta ejecutado en la infraestructura de Groq  
**Modelo:** `meta-llama/llama-guard-4-12b`  
**Tamaño:** 12 mil millones de parámetros  
**Velocidad:** Moderada (modelo grande, análisis profundo)  

### ¿Qué es?

**Llama Guard 4** es un modelo de inteligencia artificial desarrollado por **Meta** para clasificar contenido dañino en sistemas de IA conversacional. A diferencia de la capa 7 que solo detecta ataques de prompt injection, Llama Guard 4 analiza el **contenido del mensaje** en sí mismo para detectar si pertenece a alguna categoría de daño.

### ¿Qué detecta? — 13 Categorías de Riesgo

| Código | Categoría | Descripción |
|---|---|---|
| S1 | Violent Crimes | Crímenes violentos, homicidio, terrorismo |
| S2 | Non-Violent Crimes | Fraude, robo, piratería, drogas |
| S3 | Sex-Related Crimes | Delitos sexuales, trata de personas |
| S4 | Child Sexual Exploitation | Contenido sexual infantil (CSAM) |
| S5 | Defamation | Difamación, calumnias |
| S6 | Specialized Advice | Consejos médicos, legales o financieros peligrosos |
| S7 | Privacy | Violación de privacidad, doxxing |
| S8 | Intellectual Property | Piratería, plagio de contenido protegido |
| S9 | Indiscriminate Weapons | Armas de destrucción masiva, explosivos |
| S10 | Hate | Discurso de odio, discriminación |
| S11 | Suicide & Self-Harm | Suicidio y autolesión |
| S12 | Sexual Content | Contenido sexual explícito |
| S13 | Elections | Desinformación electoral |

### ¿Cómo funciona?

1. El mensaje del usuario se envía a la **API de Groq**
2. Groq ejecuta el modelo `llama-guard-4-12b` sobre el mensaje
3. El modelo responde:
   - `safe` → el mensaje es seguro, pasa al agente
   - `unsafe\nS1, S10` → el mensaje es dañino, se indica qué categorías viola
4. Si la respuesta contiene alguna categoría activa, el mensaje es bloqueado

### Categorías omitibles

El sistema permite configurar categorías a ignorar (`skip_categories`). Por ejemplo, se podría omitir `S7` (Privacidad) si el caso de uso del negocio lo requiere, sin desactivar toda la capa.

### Configuración técnica

- **Temperature: 0.0** — sin aleatoriedad, clasificación determinista
- **Fail-close:** si Groq falla, el mensaje se bloquea por precaución
- Se ejecuta **solo si el mensaje pasó la Capa 7** (Prompt Guard 2)

### Mensaje de respuesta al usuario

> *"Lo siento, no puedo continuar con esa conversación. Tu mensaje contiene contenido que no puedo procesar. Por favor, mantén un trato respetuoso."*

---

## Resumen Comparativo de las 8 Capas

| Capa | Nombre | Tecnología | Qué detecta | Requiere API externa |
|---|---|---|---|---|
| 1 | Secret Keys | REGEX | Claves de API y tokens | No |
| 2 | Prompt Injection | REGEX (60+ patrones EN+ES) | Jailbreak, manipulación del sistema, reconocimiento de infraestructura | No |
| 3 | Toxic Patterns | REGEX | Amenazas, odio, acoso, violencia, autolesión | No |
| 4 | Custom Regex | REGEX + ReDoS-safe | Patrones configurables por el admin | No |
| 5 | PII Detection | Microsoft Presidio + REGEX | DNI, RUC, email, teléfono, tarjetas | No (local) |
| 6 | URL Filter | REGEX | Links, acortadores, dominios maliciosos | No |
| 7 | Llama Prompt Guard 2 | Meta IA via Groq (86M params) | Jailbreak e injection detectados por IA | Sí (Groq API) |
| 8 | Llama Guard 4 | Meta IA via Groq (12B params) | 13 categorías de contenido dañino | Sí (Groq API) |

---

## Principio de Diseño: Defensa en Profundidad

El sistema aplica el principio de seguridad **"Defense in Depth"** (Defensa en Profundidad): en lugar de depender de una sola capa de protección, se usan múltiples capas independientes con tecnologías diferentes.

- Si un atacante evade los patrones REGEX con errores ortográficos, la IA de Meta (capa 7) lo detecta
- Si el contenido es nuevo y no está en ningún patrón, Llama Guard 4 (capa 8) lo clasifica
- Si la API de Groq no está disponible, las capas REGEX siguen funcionando
- Si Presidio no está instalado, la capa 5 usa regex como fallback

Ningún fallo en una sola capa compromete todo el sistema.

---

*Documento generado para el Programa AI Engineer — DataPath*  
*Ing. Kevin Inofuente Colque — Módulo 1, Sesión 1*
