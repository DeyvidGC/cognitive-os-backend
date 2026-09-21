# Reordenar pasos de una version

Actualizado: 2026-09-20.

`PUT /api/v1/procedure-versions/{version_id}/steps/reorder`

Body `{step_ids: [uuid, ...]}`, el orden de la lista define la nueva posicion 1..N. Requiere que `step_ids` sea exactamente una permutacion de los pasos existentes de esa version (409 si falta o sobra alguno). Solo version en `draft` (409 en otro estado). Aplica el nuevo orden en dos fases (posiciones temporales > 10000, luego 1..N) porque `UNIQUE(organization_id, version_id, position)` no es diferible. Devuelve la lista de pasos igual que `GET .../steps`.

Debe registrarse **antes** que `PUT .../steps/{step_id}` en el router: ambas rutas son PUT bajo el mismo prefijo y `{step_id}` capturaria literalmente `reorder` si quedara primero.

## Acceso y errores

require_author (owner u author); version debe pertenecer a la organizacion del token (404 si no). 409 por version no-draft o por lista invalida.

## Codigo

[Endpoint](../../../src/cognitive_os/api/v1/endpoints/procedures.py), [aplicacion](../../../src/cognitive_os/application/procedures.py) (`reorder_steps`).
