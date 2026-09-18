# Voz bidireccional en vivo con pantalla compartida

Actualizado: 2026-09-18. Implementado y probado con PostgreSQL real aislado y un
proveedor Realtime simulado; no se hizo ninguna llamada real de pago a OpenAI
Realtime ni se probo con audio real de un navegador.

`WS /api/v1/learning-sessions/{session_id}/agent/live-voice`

Protocolo distinto de [`/agent/live`](62-agent-live.md) (streaming continuo, no
turnos), para voz bidireccional real con OpenAI Realtime API, capturas
periodicas de pantalla y preguntas que el modelo hace por su cuenta sin que el
usuario le haya escrito nada. El backend media toda la conexion: nunca se
expone la API key de OpenAI ni un token efimero al navegador (a diferencia de
un WebRTC directo navegador-OpenAI), para poder reautorizar y validar cada
fragmento igual que el resto del agente en vivo.

## Handshake

Misma primera trama que `/agent/live`, dentro de 15 segundos de conectar:

```json
{"type":"auth","token":"TOKEN_LOCAL","organization_id":"UUID","consent":true}
```

El servidor responde:

```json
{"type":"ready","model":"gpt-realtime","protocol_version":1,
 "audio_input":true,"audio_output":true,"proactive_questions":true,
 "observation_interval_seconds":15,"session_max_seconds":1800}
```

`observation_interval_seconds` y `session_max_seconds` vienen de los settings
`COGNITIVE_OBSERVATION_INTERVAL_SECONDS` (5-60, por defecto 15) y
`COGNITIVE_REALTIME_SESSION_MAX_SECONDS` (60-3600, por defecto 1800).

## Mensajes cliente -> servidor

- **Audio del microfono**: tramas **binarias** WS con PCM16 crudo (sin base64,
  sin envoltorio JSON), en trozos de hasta `realtime_audio_chunk_max_bytes`
  (32 KB por defecto, configurable). Nunca se persisten.
- **Captura de pantalla**: trama de **texto** JSON, cada
  `observation_interval_seconds` segundos aproximadamente:
  ```json
  {"type":"frame","image_base64":"BASE64_JPEG_O_PNG_SIN_PREFIJO_DATA"}
  ```
  Mismo limite que `/agent/live`: JPEG o PNG, base64 sin prefijo `data:`,
  hasta 512 KB decodificado, maximo 1920x1080. El servidor la reescala a
  1280x720 JPEG antes de mandarla al modelo; nunca se guarda.
- **Responder una pregunta proactiva** (la que el modelo pregunto solo):
  ```json
  {"type":"clarification_answer","clarification_id":"UUID","text":"respuesta del usuario"}
  ```
- **Terminar la llamada desde el cliente**:
  ```json
  {"type":"end"}
  ```

## Mensajes servidor -> cliente

- **Audio de respuesta (TTS)**: tramas **binarias** WS con PCM16 crudo.
  Reproducir con Web Audio API (`AudioContext` + `AudioBufferSourceNode`, o un
  `AudioWorklet` para reproduccion en streaming).
- **Pregunta proactiva**, empujada sin que el cliente haya preguntado nada:
  ```json
  {"type":"clarification.created","clarification_id":"UUID","question":"..."}
  ```
- **Cierre de sesion**, con el motivo:
  ```json
  {"type":"session.ending","reason":"max_duration|session_status_changed|client_disconnect|error"}
  ```
  - `max_duration`: se llego al limite de duracion configurado.
  - `session_status_changed`: el token dejo de ser valido o la sesion dejo de
    estar en `capturing` (revisado periodicamente, no solo al conectar).
  - `client_disconnect`: el cliente mando `{"type":"end"}` o cerro el socket.
  - `error`: fallo el proveedor Realtime o algo inesperado.
- **Error**, igual que en `/agent/live`: `{"type":"error","status":...,"detail":"..."}`.
  `409` significa que ya hay otra sesion de voz activa para esta
  `learning_session` (solo se permite una a la vez); `401`/`403` cierran la
  conexion.

## Persistencia y efectos en la base

- La transcripcion de la llamada se guarda como `session_events` con
  `event_type = "realtime_voice_transcript"` (distinto del `transcript` que
  puede mandar el cliente por `POST .../events`; no se expone por esa ruta,
  solo la escribe este WebSocket). Cada segmento trae `{"text","speaker"}` con
  `speaker` en `user`/`assistant`.
- Si existe transcripcion de voz en vivo para la sesion, el worker
  `analyze_recording` la usa como `context["transcript"]` **en vez de**
  transcribir de nuevo el audio del video grabado con Whisper, aunque el video
  tenga `audio_consent`. El informe queda con
  `sampling.audio_exclusion_reason = "live_voice_transcript_available"` en ese
  caso (distinto de `audio_consent_not_granted`).
- Las preguntas que el modelo hace por voz se guardan como `Clarification`,
  con el mismo criterio de "una sola pregunta sin responder a la vez" que
  `/agent/live`: si ya hay una pendiente, el modelo recibe una senal de que su
  pregunta fue bloqueada y no debe insistir.
- Cada llamada crea una fila en `realtime_voice_sessions` (estado, modelo,
  motivo y hora de cierre) — ver
  [tablas de video y vectores](../base-de-datos/04-video-y-vectores.md).

## Limites y acceso

Igual que `/agent/live`: HTTP requiere Bearer y X-Organization-ID en el resto
de la API, pero el WebSocket autentica por su primera trama. Roles de captura:
owner, author, reviewer. Solo el autor de la sesion o el owner pueden abrir la
llamada. Requiere `LearningSession.status == "capturing"`; si la sesion
termina o se cierra desde otra pestana mientras la llamada sigue abierta, el
servidor la corta con `session_status_changed` en la siguiente revalidacion
periodica (`realtime_reauth_interval_seconds`, 20s por defecto).

**Nota de implementacion:** el formato exacto de eventos de la Realtime API de
OpenAI (nombres de evento, forma de `session.update`, function calling) se
implemento segun la documentacion conocida al escribir este codigo y puede
cambiar; verificar contra la documentacion vigente de OpenAI antes de depender
de un campo especifico no probado con una cuenta real, y antes de dar por
cerrada esta ficha.

[Volver a observacion y conversacion en vivo](62-agent-live.md) |
[Que debe implementar el frontend](../guias/07-mejoras-frontend.md) |
[Flujo completo y contratos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).
