# DataBot — Agente IA Multi-Tool con Seguridad

Asistente virtual inteligente para **DATAPATH**, construido con LangChain y GPT-4.1. Responde consultas sobre programas, cursos, precios e inscripciones usando RAG (Pinecone), búsqueda en internet (Tavily) y memoria persistente (PostgreSQL). Se integra con **Chatwoot** vía webhook para atención automatizada con handoff a humanos.

---

## Arquitectura

```
Usuario (WhatsApp / Web)
        │
        ▼
   Chatwoot  ──webhook──▶  FastAPI (/webhook)
                                  │
                          InputGuardrail (8 capas)
                                  │ (si pasa)
                               Agente IA
                           ┌──────┼──────┐
                    buscar_      buscar_  obtener_
                    datapath    internet  fecha_hora
                    (Pinecone)  (Tavily)  (stdlib)
                                  │
                           PostgreSQL (historial)
```

---

## Herramientas del Agente

| Tool | Descripción |
|---|---|
| `buscar_datapath` | RAG sobre la base de conocimiento de DATAPATH (Pinecone + `text-embedding-ada-002`) |
| `buscar_internet` | Búsqueda web contextualizada a DATAPATH via Tavily |
| `obtener_fecha_hora` | Fecha y hora actual por zona horaria IANA (sin APIs externas) |

---

## Capas de Seguridad (InputGuardrail)

El pipeline de seguridad valida **cada mensaje entrante** antes de llegar al agente:

| Capa | Tecnología | Qué detecta |
|---|---|---|
| 1 | REGEX | API keys y tokens secretos (`sk-...`, `ghp_...`, `AIza...`) |
| 2 | REGEX | Prompt injection, jailbreak, reconocimiento de infraestructura (EN + ES) |
| 3 | REGEX | Amenazas, hate speech, acoso sexual, incitación a la violencia, autolesión |
| 4 | REGEX (ReDoS-safe) | Patrones personalizados configurables por el admin |
| 5 | Presidio (Microsoft) | PII: DNI, RUC, email, teléfono peruano |
| 6 | REGEX | URLs, acortadores y dominios en blacklist |
| 7 | Llama Prompt Guard 2 (Groq) | Jailbreak/injection por IA (86M params, 8 idiomas) |
| 8 | GPT-OSS-Safeguard (Groq) | NSFW, violencia, odio, autolesión (20B params) |

---

## Integración con Chatwoot

- **Etiqueta `atiende-ia`**: activa el bot en una conversación.
- **Etiqueta `ia-off`**: desactiva la IA — el bot no responde.
- **Handoff automático**: si el usuario pide hablar con un humano, el bot agrega `ia-off`, elimina `atiende-ia` y envía un mensaje de despedida.
- El historial de conversación se asocia al `conversation_id` de Chatwoot mediante un UUID determinista.

---

## Estructura del Proyecto

```
.
├── main_chatwoot-ia_off.py                  # Webhook FastAPI + lógica Chatwoot
├── agente_basico_hc_bc_toolexterna_pinecone.py  # Agente principal (tools + memoria)
├── tools/
│   ├── Base_de_conocimiento.py              # Tool RAG con Pinecone
│   ├── Busqueda_internet.py                 # Tool Tavily
│   └── Hora_y_fecha.py                      # Tool fecha/hora
├── guardrails/
│   ├── input_guardrail.py                   # Orquestador de seguridad (8 capas)
│   ├── pii_detector.py                      # Capa 5 — Presidio
│   └── llama_guard_service.py               # Capas 7 y 8 — LlamaGuard via Groq
├── requirements.txt
└── .env                                     # Variables de entorno (no subir a git)
```

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd LangChain-AgenteIA-MultiTool-Seguridad

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Modelo de spaCy para PII (Capa 5)
python -m spacy download es_core_news_sm
```

---

## Configuración (.env)

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Pinecone (Base de Conocimiento)
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=langchain-pinecone-asistente-de-ventas

# Tavily (Búsqueda internet)
TAVILY_API_KEY=tvly-...

# PostgreSQL (Historial de conversación)
DB_USER=postgres
DB_PASSWORD=...
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres

# Chatwoot
CHATWOOT_BASE_URL=https://app.chatwoot.com
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_API_ACCESS_TOKEN=...
CHATWOOT_BOT_LABEL=atiende-ia

# Groq (Capas 7 y 8 — opcional)
GROQ_API_KEY=gsk_...

# Zona horaria del agente
AGENT_TIMEZONE=America/Lima
```

---

## Ejecución

### Modo Chatwoot (webhook)

```bash
python main_chatwoot-ia_off.py
# Servidor en http://0.0.0.0:8000
```

Endpoints disponibles:

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/webhook` | Recibe eventos de Chatwoot |
| `POST` | `/test` | Prueba el agente sin Chatwoot |
| `GET` | `/health` | Estado del servicio |
| `GET` | `/` | Info del servicio |

### Modo consola (sin Chatwoot)

```bash
python agente_basico_hc_bc_toolexterna_pinecone.py
```

---

## Autor

**Ing. Kevin Inofuente Colque** — [DataPath](https://datapath.pe)  
Módulo 1 — Sesión 1 — Programa AI Engineer
