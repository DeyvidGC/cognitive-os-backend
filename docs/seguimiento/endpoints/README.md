# Endpoints

Actualizacion 2026-09-20: [4 rutas nuevas y 2 permisos endurecidos para el rediseno de frontend](rediseno-2026-09-20.md).
Actualizacion 2026-09-16: [24 rutas HTTP visuales y un WebSocket](visual-catalogo.md).
El catalogo inferior conserva las rutas previas.

Corte documental: 2026-09-13. 35 operaciones versionadas obtenidas del OpenAPI del codigo, mas 2 rutas heredadas.

Cada ficha explica una operacion; los ejemplos usan datos ficticios. Los UUID se obtienen de las respuestas anteriores.

Ver [convenciones y errores](../guias/02-probar-api.md) y [diagramas](../guias/01-arquitectura.md).

| Metodo y ruta | Explicacion |
| --- | --- |
| `GET /api/v1/health` | [Estado de la API](01-health.md) |
| `POST /api/v1/auth/register` | [Registrar cuenta](02-register.md) |
| `POST /api/v1/auth/login` | [Iniciar sesion](03-login.md) |
| `GET /api/v1/auth/me` | [Consultar mi perfil](04-me.md) |
| `POST /api/v1/auth/logout` | [Cerrar sesion](05-logout.md) |
| `POST /api/v1/learning-sessions` | [Crear sesion de aprendizaje](06-create-session.md) |
| `GET /api/v1/learning-sessions` | [Listar sesiones](07-list-sessions.md) |
| `GET /api/v1/learning-sessions/{session_id}` | [Consultar una sesion](08-get-session.md) |
| `POST /api/v1/learning-sessions/{session_id}/events` | [Registrar un evento](09-add-event.md) |
| `GET /api/v1/learning-sessions/{session_id}/events` | [Listar eventos](10-list-events.md) |
| `POST /api/v1/learning-sessions/{session_id}/finish` | [Cerrar captura y crear trabajo](11-finish-session.md) |
| `GET /api/v1/jobs/{job_id}` | [Consultar un trabajo](12-get-job.md) |
| `POST /api/v1/procedures` | [Crear procedimiento](13-create-procedure.md) |
| `GET /api/v1/procedures` | [Listar procedimientos](14-list-procedures.md) |
| `POST /api/v1/procedures/{procedure_id}/versions` | [Crear borrador de version](15-create-version.md) |
| `GET /api/v1/procedures/{procedure_id}/versions` | [Listar versiones](16-list-versions.md) |
| `GET /api/v1/procedure-versions/{version_id}` | [Consultar una version](17-get-version.md) |
| `POST /api/v1/procedure-versions/{version_id}/steps` | [Crear paso](18-create-step.md) |
| `GET /api/v1/procedure-versions/{version_id}/steps` | [Listar pasos](19-list-steps.md) |
| `PUT /api/v1/procedure-versions/{version_id}/steps/{step_id}` | [Actualizar paso](20-update-step.md) |
| `PUT /api/v1/procedure-versions/{version_id}/tutorial` | [Guardar tutorial](21-write-tutorial.md) |
| `GET /api/v1/procedure-versions/{version_id}/tutorial` | [Consultar tutorial](22-get-tutorial.md) |
| `POST /api/v1/procedure-versions/{version_id}/submit` | [Enviar a revision](23-submit.md) |
| `POST /api/v1/procedure-versions/{version_id}/return` | [Devolver a borrador](24-return-to-draft.md) |
| `POST /api/v1/procedure-versions/{version_id}/approve` | [Aprobar version](25-approve.md) |
| `POST /api/v1/procedure-versions/{version_id}/publish` | [Publicar version](26-publish.md) |
| `POST /api/v1/procedure-versions/{version_id}/retire` | [Retirar version publicada](27-retire.md) |
| `GET /api/v1/knowledge/search` | [Buscar conocimiento publicado](28-search-knowledge.md) |
| `POST /api/v1/learning-sessions/{session_id}/evidence` | [Subir captura](29-upload-evidence.md) |
| `GET /api/v1/learning-sessions/{session_id}/evidence` | [Listar capturas](30-list-evidence.md) |
| `GET /api/v1/evidence/{evidence_id}/file` | [Descargar captura](31-download-evidence.md) |
| `PUT /api/v1/procedure-versions/{version_id}/steps/{step_id}/evidence` | [Vincular captura a un paso](32-link-evidence.md) |
| `POST /api/v1/learning-sessions/{session_id}/clarifications` | [Plantear aclaracion](33-create-clarification.md) |
| `GET /api/v1/learning-sessions/{session_id}/clarifications` | [Listar aclaraciones](34-list-clarifications.md) |
| `PUT /api/v1/learning-sessions/{session_id}/clarifications/{clarification_id}/answer` | [Responder aclaracion](35-answer-clarification.md) |
| `GET /` | [Compatibilidad](36-root.md) |
| `GET /hello/{name}` | [Compatibilidad](37-hello.md) |
