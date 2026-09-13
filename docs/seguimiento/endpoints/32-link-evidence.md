# Vincular captura a un paso

[Indice](README.md) | [Contratos de datos](contratos.md)

`PUT /api/v1/procedure-versions/{version_id}/steps/{step_id}/evidence`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Valida organizacion, paso y evidencia. Si la version tiene source_session_id, la evidencia debe ser de esa sesion. Inserta o actualiza la explicacion del enlace y devuelve metadatos de evidencia.

## Acceso

owner o author; version draft.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `version_id` | path | Si | string (uuid); - |
| `step_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Cuerpo: `application/json`.

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `evidence_id` | string (uuid) | Si | - |
| `explanation` | string | Si | min. caracteres: 1; max. caracteres: 4000 |

Ejemplo orientativo; sustituir IDs simbolicos y no usar esta clave en cuentas reales:

```json
{
  "evidence_id": "REEMPLAZAR_POR_UUID_DE_EVIDENCIA",
  "explanation": "La captura muestra el resultado del paso."
}
```

## Respuesta

Exito: **200**. `EvidenceResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

procedure_versions, steps, evidence, step_evidence, audit_events.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/evidence.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
