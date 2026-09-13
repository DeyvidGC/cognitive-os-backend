# Registrar un evento

[Indice](README.md) | [Contratos de datos](contratos.md)

`POST /api/v1/learning-sessions/{session_id}/events`

Estado: implementado en codigo al 2026-09-13. Requiere conexion SQL configurada salvo health; no implica que el servidor este disponible permanentemente.

## Para que sirve

Admite message y transcript durante capturing. Misma clave y contenido devuelve el evento previo incluso despues del cierre; contenido distinto o secuencia duplicada responde 409. No ejecuta IA.

## Acceso

Autor de la sesion u owner; rol author/owner.

Enviar `Authorization: Bearer <token>`. Enviar tambien `X-Organization-ID`; el servidor comprueba la membresia.

## Entrada

| Parametro | Ubicacion | Obligatorio | Tipo y reglas |
| --- | --- | --- | --- |
| `session_id` | path | Si | string (uuid); - |
| `x-organization-id` | header | Si | string (uuid); - |

Cuerpo: `application/json`.

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `idempotency_key` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `sequence_number` | integer | Si | minimo: 0; maximo: 9223372036854776000 |
| `offset_ms` | integer | Si | minimo: 0; maximo: 9223372036854776000 |
| `event_type` | string | Si | `message`, `transcript` |
| `text` | string | Si | min. caracteres: 1; max. caracteres: 20000 |

Ejemplo orientativo; sustituir IDs simbolicos y no usar esta clave en cuentas reales:

```json
{
  "idempotency_key": "evento-001",
  "sequence_number": 0,
  "offset_ms": 0,
  "event_type": "message",
  "text": "Abro la pantalla de cotizaciones."
}
```

## Respuesta

Exito: **200**. `EventResponse`. Campos y tipos en [contratos](contratos.md). Las listas son arrays JSON sin envoltorio total/items.

## Persistencia y limites

learning_sessions, session_events.

Errores transversales: 422 por entrada invalida; 503 si falta conexion o migraciones. En rutas protegidas, 401 por token y 403 por permisos. Los conflictos de estado o unicidad usan 409 y los recursos no encontrados 404 cuando corresponda. Register/login tambien pueden devolver 429 por limite de intentos. Ver las condiciones concretas anteriores; no todas las rutas emiten todos los codigos.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/sessions.py) y [dependencias de acceso](../../../src/cognitive_os/api/dependencies.py). [Modelos SQLAlchemy](../../../src/cognitive_os/infrastructure/database/models.py).
