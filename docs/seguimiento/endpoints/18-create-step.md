# Crear paso

[Indice](README.md) | [Contratos de datos](contratos.md)

`POST /api/v1/procedure-versions/{version_id}/steps`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Agrega instrucciones, resultado esperado, origen y validacion. La posicion es unica en la version. Un paso confirmed todavia requiere revision del procedimiento.

## Acceso

owner o author; version draft.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `version_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Cuerpo: `application/json`.

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `position` | integer | Si | minimo: 1; maximo: 10000 |
| `instruction` | string | Si | min. caracteres: 1; max. caracteres: 10000 |
| `expected_result` | string | Si | min. caracteres: 1; max. caracteres: 10000 |
| `origin` | string | Si | `observed`, `user_explained`, `inferred` |
| `validation_status` | string | No | defecto: "pending"; `pending`, `confirmed`, `rejected` |

Ejemplo orientativo; sustituir IDs simbolicos y no usar esta clave en cuentas reales:

```json
{
  "position": 1,
  "instruction": "Registrar los datos de la cotizacion.",
  "expected_result": "Cotizacion guardada.",
  "origin": "user_explained",
  "validation_status": "confirmed"
}
```

## Respuesta

Exito: **201**. `StepResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

procedure_versions, steps, audit_events.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/procedures.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
