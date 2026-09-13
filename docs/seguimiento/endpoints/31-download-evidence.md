# Descargar captura

[Indice](README.md) | [Contratos de datos](contratos.md)

`GET /api/v1/evidence/{evidence_id}/file`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Valida organizacion y ruta local antes de devolver el archivo como adjunto. No crea un enlace publico. Archivo faltante o evidencia ajena responde 404.

## Acceso

owner, author o reviewer.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `evidence_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Sin cuerpo de solicitud.

## Respuesta

Exito: **200**. Archivo binario con su tipo de imagen y Content-Disposition de adjunto. El OpenAPI actual muestra un esquema generico; el comportamiento real es FileResponse.

## Persistencia y limites

evidence; archivo local.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/evidence.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
