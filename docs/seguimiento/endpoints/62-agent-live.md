# Observacion y conversacion en vivo

Actualizado: 2026-09-16.

`WS /api/v1/learning-sessions/{session_id}/agent/live`

Primera trama auth: {type:auth, token, organization_id, consent:true}. Luego {type:observe|message, message_id:UUID, text?, image_base64?}. Imagen JPEG/PNG base64 sin data URL. Retorna ready, processing y reply; la respuesta contiene message_id y el objeto reply con observation/answer/questions. Errores status/detail. Token fuera de URL, Origin autorizado, reautenticacion por turno. Capturas efimeras; texto persistido. No audio en vivo.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).
