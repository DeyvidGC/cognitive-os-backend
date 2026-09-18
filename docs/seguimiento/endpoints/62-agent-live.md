# Observacion y conversacion en vivo

Actualizado: 2026-09-18.

`WS /api/v1/learning-sessions/{session_id}/agent/live`

Primera trama auth: {type:auth, token, organization_id, consent:true}. Luego {type:observe|message, message_id:UUID, text?, image_base64?}. Imagen JPEG/PNG base64 sin data URL. Retorna ready, processing y reply; la respuesta contiene message_id y el objeto reply con observation/answer/questions. Errores status/detail. Token fuera de URL, Origin autorizado, reautenticacion por turno. Capturas efimeras; texto persistido. Sin audio; ver `/agent/live-voice` para voz bidireccional.

## `WS /api/v1/learning-sessions/{session_id}/agent/live-voice`

Protocolo distinto de `/agent/live` (streaming continuo, no turnos), pensado para
voz bidireccional real con OpenAI Realtime, capturas periodicas de pantalla y
preguntas que el modelo hace por su cuenta. El backend media toda la conexion:
nunca se expone la API key de OpenAI ni un token efimero al navegador.

Misma primera trama que `/agent/live`: `{type:auth, token, organization_id, consent:true}`.
El servidor responde:

```json
{"type":"ready","model":"gpt-realtime","audio_input":true,"audio_output":true,
 "proactive_questions":true,"observation_interval_seconds":15,"session_max_seconds":1800}
```

Despues de `ready`:
- **Audio del microfono**: tramas binarias WS con PCM16 crudo, en trozos de hasta
  `realtime_audio_chunk_max_bytes` (32 KB por defecto). Nunca se persisten.
- **Audio de respuesta (TTS)**: el servidor envia tramas binarias con PCM16; reproducir
  con Web Audio API.
- **Capturas de pantalla**: trama de texto `{"type":"frame","image_base64":"..."}` cada
  `observation_interval_seconds` segundos (mismo limite de tamano/formato que en
  `/agent/live`: JPEG/PNG, base64 sin prefijo `data:`, hasta 512 KB).
- **Responder una pregunta proactiva**: `{"type":"clarification_answer","clarification_id":"UUID","text":"..."}`.
- **Terminar la llamada desde el cliente**: `{"type":"end"}`.

El servidor puede enviar en cualquier momento, sin que el cliente haya preguntado nada:

```json
{"type":"clarification.created","clarification_id":"UUID","question":"..."}
```

y al cerrar la sesion (por TTL, cambio de estado de la sesion, `end` del cliente
o error): `{"type":"session.ending","reason":"max_duration|session_status_changed|client_disconnect|error"}`.

Solo una sesion de voz activa por `learning_session`; una segunda conexion mientras
la primera sigue activa recibe `{"type":"error","status":409,...}`. El servidor
revalida token/organizacion/estado de la sesion periodicamente (no solo al conectar);
si deja de cumplirse, cierra con `session_status_changed`. Duracion maxima por
defecto 30 minutos (`realtime_session_max_seconds`).

La transcripcion de la conversacion de voz se guarda como eventos de sesion
(`event_type: realtime_voice_transcript`, no visibles por `POST .../events`) y
alimenta el mismo analisis visual que un video subido: si existe, el worker
`analyze_recording` no vuelve a transcribir el audio del video con Whisper.
Las preguntas que el modelo hace por voz se guardan como `Clarification`, igual
que en `/agent/live`.

**Nota de implementacion:** el formato exacto de eventos de la Realtime API de
OpenAI (nombres, forma de `session.update`, function calling) puede cambiar;
verificar contra la documentacion vigente de OpenAI antes de depender de un
campo especifico no probado con una cuenta real.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).
