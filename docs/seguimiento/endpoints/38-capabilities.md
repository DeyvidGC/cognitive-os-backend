# Limites y servicios disponibles

Actualizado: 2026-09-16.

`GET /api/v1/recordings/capabilities`

Sin body. Devuelve media_types, max_bytes, max_seconds, storage_configured, audio_supported, live_observation y modelos. storage_configured solo indica configuracion presente, no conectividad probada.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

