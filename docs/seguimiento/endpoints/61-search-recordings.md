# Busqueda semantica de videos

Actualizado: 2026-09-16.

`POST /api/v1/recordings/search`

Body {query: texto 1..1200 caracteres, limit:1..20}. Genera vector de consulta y devuelve results con contenido, fuente, score, grabacion y revision. Solo organizacion actual e informes aprobados vigentes. 503 sin proveedor. No es chat RAG ni busqueda de procedimientos textuales.

## Acceso y errores

HTTP requiere Bearer y X-Organization-ID. Roles de captura: owner, author, reviewer;
reader no accede a videos/informes originales. Los cambios que requieren escritor
respetan autor de sesion y rol owner. Recursos de otra organizacion retornan 404.
Errores HTTP comunes: 401 sesion expirada, 403 permiso, 409 conflicto y 422 contrato.
El WebSocket autentica por su primera trama, no por esos encabezados HTTP.

[Flujo completo y ejemplos](../guias/06-aprendizaje-visual.md) |
[Base de datos y vectores](../base-de-datos/04-video-y-vectores.md).

