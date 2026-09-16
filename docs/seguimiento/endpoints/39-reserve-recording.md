# Reservar video

Actualizado: 2026-09-16.

`POST /api/v1/learning-sessions/{session_id}/recordings`

Body: idempotency_key UUID, media_type, size_bytes, consent:true, audio_consent opcional y content_sha256 opcional. Retorna Recording (201). Una reserva por sesion; repetir datos conserva ID; diferencias dan 409. Requiere escritor y sesion capturando.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

