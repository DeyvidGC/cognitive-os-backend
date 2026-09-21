# Busqueda unificada (video + procedimientos)

Actualizado: 2026-09-20.

`POST /api/v1/search`

Body {query: texto 1..1200 caracteres, limit:1..20}. Une en una sola llamada la busqueda vectorial de videos ([61-search-recordings.md](61-search-recordings.md), via `search_vectors`) y la busqueda textual de procedimientos publicados ([28-search-knowledge.md](28-search-knowledge.md), via `procedures.search_knowledge`), normalizadas a `{type: "video"|"procedure", score, snippet, timestamp_ms?, recording_id?, session_id?, procedure_id?, version_id?, step_id?}` y ordenadas por score descendente.

`score` de tipo `procedure` es `ts_rank / (ts_rank + 1)` para acercarlo a la escala 0..1 del coseno de video; es una heuristica de mezcla, no una normalizacion exacta comparable entre tipos. No reemplaza `/recordings/search` ni `/knowledge/search`, que siguen existiendo con su forma original.

## Acceso y errores

Mismo gate que la busqueda de video: owner, author o reviewer (`CaptureMember`), no reader. HTTP requiere Bearer y X-Organization-ID. 503 si el proveedor de embeddings no esta configurado. Recursos de otra organizacion nunca aparecen (join por organization_id en ambas fuentes).

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/search.py), [aplicacion](../../../src/cognitive_os/application/search.py).
