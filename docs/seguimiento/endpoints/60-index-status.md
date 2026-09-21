# Comprobar indice vectorial

Actualizado: 2026-09-20.

`GET /api/v1/recordings/{recording_id}/index`

Devuelve indexed, chunks, model, dimensions:1536, recording_id y revision. Cuenta solo modelo configurado/revision vigente. indexed:false no indica por si solo un fallo; revisar jobs por sesion.

## Acceso y errores

**Cambio 2026-09-20**: antes owner, author o reviewer; ahora solo **owner** (contadores de indexacion son vista de operacion, ver [12-get-job.md](12-get-job.md)).
HTTP requiere Bearer y X-Organization-ID. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

