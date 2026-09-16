# Reproducir video privado

Actualizado: 2026-09-16.

`GET /api/v1/recordings/{recording_id}/playback`

Retorna SignedTransfer GET, headers vacios, SAS de 5 minutos sobre snapshot; MIME video e inline. Asignar url a video.src. 409 si no se completo. No reenviar Bearer a Azure. Renovar URL vencida y restaurar currentTime.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

