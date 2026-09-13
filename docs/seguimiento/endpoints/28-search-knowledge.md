# Buscar conocimiento publicado

[Indice](README.md) | [Contratos de datos](contratos.md)

`GET /api/v1/knowledge/search`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Busqueda textual en espanol con websearch_to_tsquery y ts_rank. Filtra published y organizacion; devuelve fragmentos con version y paso, sin respuesta generada por IA. rank no es probabilidad de verdad ni similitud vectorial.

## Acceso

Cualquier miembro de la organizacion.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `q` | query | Si | string; min. caracteres: 1; max. caracteres: 500 |
| `limit` | query | No | integer; minimo: 1; maximo: 100; defecto: 10 |
| `x-organization-id` | header | Si | string (uuid); - |

Sin cuerpo de solicitud.

## Respuesta

Exito: **200**. `lista de KnowledgeResult`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

knowledge_chunks, procedure_versions.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/procedures.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
