# Listar sesiones

[Indice](README.md) | [Contratos de datos](contratos.md)

`GET /api/v1/learning-sessions`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Lista las sesiones de la organizacion seleccionada, por fecha descendente e ID. No se limita a las sesiones del autor. Tiene limit/offset.

## Acceso

owner, author o reviewer.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `limit` | query | No | integer; minimo: 1; maximo: 100; defecto: 20 |
| `offset` | query | No | integer; minimo: 0; defecto: 0 |
| `x-organization-id` | header | Si | string (uuid); - |

Sin cuerpo de solicitud.

## Respuesta

Exito: **200**. `lista de SessionResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

learning_sessions.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/sessions.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
