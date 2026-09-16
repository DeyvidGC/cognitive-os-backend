# Encolar analisis

Actualizado: 2026-09-16.

`POST /api/v1/recordings/{recording_id}/process`

Sin body. Retorna Job (202), kind analyze_recording. Exige uploaded; equivalencia con finish-session. Idempotente: devuelve el mismo trabajo, no genera dos informes.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

