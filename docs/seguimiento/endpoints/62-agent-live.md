# Observacion y conversacion en vivo

Actualizado: 2026-09-18.

`WS /api/v1/learning-sessions/{session_id}/agent/live`

Primera trama auth: {type:auth, token, organization_id, consent:true}. Luego {type:observe|message, message_id:UUID, text?, image_base64?}. Imagen JPEG/PNG base64 sin data URL. Retorna ready, processing y reply; la respuesta contiene message_id y el objeto reply con observation/answer/questions. Errores status/detail. Token fuera de URL, Origin autorizado, reautenticacion por turno. Capturas efimeras; texto persistido. Sin audio.

Para voz bidireccional real (microfono, TTS, capturas periodicas y preguntas
proactivas del modelo) usar el endpoint hermano
[`/agent/live-voice`](63-agent-live-voice.md) en vez de este; el protocolo es
distinto (streaming continuo, no por turnos) y tiene su propia ficha.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).
