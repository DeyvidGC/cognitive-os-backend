# Consultar un trabajo

[Indice](README.md) | [Contratos de datos](contratos.md)

`GET /api/v1/jobs/{job_id}`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Devuelve estado y contadores del job de la organizacion. No lo ejecuta, reintenta ni cancela. No expone last_error ni datos internos del lease.

## Acceso

owner, author o reviewer.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `job_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Sin cuerpo de solicitud.

## Respuesta

Exito: **200**. `JobResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

jobs.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/sessions.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
