# Responder aclaracion

[Indice](README.md) | [Contratos de datos](contratos.md)

`PUT /api/v1/learning-sessions/{session_id}/clarifications/{clarification_id}/answer`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Guarda answer, answered_by y resolved_at. Puede actualizarse mientras la sesion captura; despues del cierre no se aceptan respuestas.

## Acceso

Autor de la sesion u owner; rol author/owner, sesion capturing.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `session_id` | path | Si | string (uuid); - |
| `clarification_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Cuerpo: `application/json`.

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `answer` | string | Si | min. caracteres: 1; max. caracteres: 10000 |

Ejemplo orientativo; sustituir IDs simbolicos y no usar esta clave en cuentas reales:

```json
{
  "answer": "El supervisor comercial."
}
```

## Respuesta

Exito: **200**. `ClarificationResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

learning_sessions, clarifications.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/clarifications.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
