---
name: message-concatenation-buffer
description: Cómo está implementado en DataBot el buffer + debounce con Redis que concatena mensajes seguidos del usuario (WhatsApp/Chatwoot) en una sola respuesta del agente. Úsalo al tocar el flujo del webhook (main_chatwoot-ia_off.py), el módulo message_buffer/, las variables MESSAGE_BUFFER_*/REDIS_*, o al depurar respuestas duplicadas / concatenación de mensajes en este proyecto.
---

# Buffer de concatenación de mensajes — DataBot (implementación de este proyecto)

Este proyecto (agente DataBot para Chatwoot/WhatsApp) implementa un **buffer con debounce en Redis** para que, cuando el usuario manda varios mensajes seguidos ("hola" / "todo bien?" / "tengo una consulta"), el agente NO responda a cada uno: los acumula, los concatena y produce **una sola respuesta**.

> Patrón genérico y reutilizable: ver la skill global `message-concatenation-buffer` (`~/.claude/skills/`). Este archivo documenta el cableado **concreto de este repo**.

## Archivos involucrados

```
message_buffer/
├── __init__.py        ← API pública: encolar_mensaje, BUFFER_ENABLED, BUFFER_WINDOW_SECONDS
├── config.py          ← lee MESSAGE_BUFFER_* del .env (ENABLED, WINDOW_SECONDS, TTL_SECONDS, SEPARATOR)
├── redis_client.py    ← cliente redis.asyncio singleton (REDIS_URL o granulares + REDIS_TLS)
└── buffer.py          ← encolar_mensaje() + _esperar_y_procesar() + _limpiar_concatenacion()

main_chatwoot-ia_off.py  ← el webhook encola en el buffer en vez de responder por mensaje
requirements.txt         ← redis>=5.0
.env.example             ← bloque REDIS_* y MESSAGE_BUFFER_*
```

## Flujo en el webhook (`main_chatwoot-ia_off.py`)

1. Llega el webhook `message_created` / `incoming` (descarta otros, y los que tengan el tag `ia-off`).
2. En vez de llamar al agente directo, el handler:
   - Define un callback async `_procesar_concatenacion(conv_id, mensaje_concatenado)` que ejecuta el agente en un hilo: `await asyncio.to_thread(ejecutar_agente_y_responder, conv_id, contact_id, mensaje_concatenado)`.
   - Llama `await encolar_mensaje(conversation_id, message_content, _procesar_concatenacion)` y retorna `{"status": "buffered"}` de inmediato (ACK rápido a Chatwoot).
3. `ejecutar_agente_y_responder()` (helper síncrono) arma `tools_extra` (handoff `transferir_a_humano`), llama `chat_con_agente(...)` y hace `send_chatwoot_message(...)`.
4. Si `MESSAGE_BUFFER_ENABLED=false`, el webhook ejecuta el agente directo (modo mensaje-por-mensaje, fallback).

## Debounce por secuencia (`buffer.py`)

Claves Redis por conversación:
- `databot:buffer:msgs:{conv}` → lista de mensajes (`RPUSH`)
- `databot:buffer:seq:{conv}`  → contador de secuencia (`INCR`)

`encolar_mensaje`: pipeline `RPUSH + INCR + EXPIRE×2`, captura `mi_seq`, programa `asyncio.create_task(_esperar_y_procesar(...))` (referencia guardada en el set `_tareas` para que el GC no la cancele).

`_esperar_y_procesar`: `sleep(WINDOW_SECONDS)` → si `seq` ya no es `mi_seq`, aborta (llegó algo nuevo) → si gana, `LRANGE`, concatena con `SEPARATOR` y llama al callback.

## Limpieza tras responder (requisito clave de este proyecto)

La concatenación **siempre se elimina una vez el agente respondió** — solo sirve para 1 inferencia. Está en un `finally` dentro de `_esperar_y_procesar`, vía `_limpiar_concatenacion()`:

- Si NO llegaron mensajes nuevos durante la respuesta (`seq` sigue siendo `mi_seq`) → `DELETE msgs_key seq_key`.
- Si SÍ llegaron nuevos → `LTRIM msgs_key n -1` (quita solo los ya respondidos; conserva los nuevos para la siguiente inferencia).

Logs de referencia: `[BUFFER] Concatenando N mensaje(s) → 1 respuesta` y `[BUFFER] 🧹 Concatenación eliminada tras responder`.

## Variables de entorno (ver `.env.example`)

```env
# Redis (opción granular, la que usa este proyecto en Redis Cloud)
REDIS_HOST=redis-xxxxx.cloud.redislabs.com
REDIS_PORT=xxxxx
REDIS_DB=0                 # índice numérico del DB lógico, NO el nombre del panel
REDIS_PASSWORD=...
REDIS_TLS=false            # true solo si el Redis exige cifrado
#REDIS_URL=               # alternativa de una sola línea (tiene precedencia si está set)

MESSAGE_BUFFER_ENABLED=true
MESSAGE_BUFFER_WINDOW_SECONDS=15   # ventana de silencio (preferencia del autor: 15s)
MESSAGE_BUFFER_TTL_SECONDS=300
MESSAGE_BUFFER_SEPARATOR="\n"
```

## Probar / depurar

- Levantar: `python main_chatwoot-ia_off.py` (uvicorn en `:8000`). Mirar logs `[REDIS]` y `[BUFFER]`.
- Si responde por mensaje en vez de concatenar: revisar `MESSAGE_BUFFER_ENABLED` y la conexión Redis (`[REDIS] Cliente creado…`).
- El guardrail de seguridad corre sobre el **texto concatenado** (dentro de `chat_con_agente`): si un mensaje de la ráfaga es malicioso, se bloquea todo el conjunto.

## No cambiar sin querer

- No borrar el buffer **antes** de llamar al agente: rompería el requisito de "limpiar después de responder" y podría perder mensajes que lleguen durante la inferencia.
- Mantener el `to_thread`: `chat_con_agente` es bloqueante; correrlo directo en el handler async bloquea el event loop de FastAPI.
