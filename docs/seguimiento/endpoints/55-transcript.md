# Transcripcion y consentimiento

Actualizado: 2026-09-16.

`GET /api/v1/recordings/{recording_id}/transcript`

Retorna text, revision, audio_present, analyzed, model y exclusion_reason. Sin audio o consentimiento no inventa texto. Se habilita despues de que exista un informe, no durante captura.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

