# Subir captura

[Indice](README.md) | [Contratos de datos](contratos.md)

`POST /api/v1/learning-sessions/{session_id}/evidence`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Multipart file. Valida PNG/JPEG/WebP reales y limite predeterminado de 10 MiB. Genera ruta local y hash. captured_at es la hora de recepcion. No analiza la imagen ni crea un evento automaticamente.

## Acceso

Autor de la sesion u owner; rol author/owner, sesion capturing.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `session_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Cuerpo: `multipart/form-data`.

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `file` | string | Si | - |

En Swagger usar Choose File en `file`. No enviar el binario como JSON ni una ruta del cliente.

## Respuesta

Exito: **201**. `EvidenceResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

learning_sessions, evidence; archivo en .data/evidence.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/evidence.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
