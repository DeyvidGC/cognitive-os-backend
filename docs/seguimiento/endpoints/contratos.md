# Contratos Pydantic

[Indice de endpoints](README.md)

Extraidos del OpenAPI del codigo el 2026-09-13. Los campos obligatorios deben enviarse en solicitudes o estaran presentes en respuestas; un campo nullable puede ser obligatorio y aceptar null. Los contratos no son tablas SQL.

## Body_upload_evidence_api_v1_learning_sessions__session_id__evidence_post

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `file` | string | Si | - |

## ClarificationAnswer

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `answer` | string | Si | min. caracteres: 1; max. caracteres: 10000 |

## ClarificationCreate

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `question` | string | Si | min. caracteres: 1; max. caracteres: 4000 |

## ClarificationResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `session_id` | string (uuid) | Si | - |
| `question` | string | Si | - |
| `answer` | string o null | Si | - |
| `answered_by` | string (uuid) o null | Si | - |
| `resolved_at` | string (date-time) o null | Si | - |
| `created_at` | string (date-time) | Si | - |

## EventCreate

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `idempotency_key` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `sequence_number` | integer | Si | minimo: 0; maximo: 9223372036854776000 |
| `offset_ms` | integer | Si | minimo: 0; maximo: 9223372036854776000 |
| `event_type` | string | Si | `message`, `transcript` |
| `text` | string | Si | min. caracteres: 1; max. caracteres: 20000 |

## EventResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `session_id` | string (uuid) | Si | - |
| `sequence_number` | integer | Si | - |
| `idempotency_key` | string | Si | - |
| `event_type` | string | Si | - |
| `offset_ms` | integer | Si | - |
| `payload` | object | Si | - |
| `created_at` | string (date-time) | Si | - |

## EvidenceLink

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `evidence_id` | string (uuid) | Si | - |
| `explanation` | string | Si | min. caracteres: 1; max. caracteres: 4000 |

## EvidenceResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `session_id` | string (uuid) | Si | - |
| `media_type` | string | Si | - |
| `size_bytes` | integer | Si | - |
| `sha256` | string | Si | - |
| `captured_at` | string (date-time) | Si | - |

## HTTPValidationError

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `detail` | lista de ValidationError | No | - |

## HealthResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `status` | string | Si | valor obligatorio: "ok" |

## JobResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `session_id` | string (uuid) o null | Si | - |
| `kind` | string | Si | - |
| `status` | string | Si | - |
| `attempts` | integer | Si | - |
| `created_at` | string (date-time) | Si | - |
| `completed_at` | string (date-time) o null | Si | - |

## KnowledgeResult

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `procedure_id` | string (uuid) | Si | - |
| `version_id` | string (uuid) | Si | - |
| `version_number` | integer | Si | - |
| `step_id` | string (uuid) o null | Si | - |
| `content` | string | Si | - |
| `rank` | number | Si | - |

## LoginRequest

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `email` | string (email) | Si | - |
| `password` | string (password) | Si | min. caracteres: 1; max. caracteres: 128 |

## MembershipResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `organization_id` | string (uuid) | Si | - |
| `organization_name` | string | Si | - |
| `role` | string | Si | `owner`, `author`, `reviewer`, `reader` |

## ProcedureCreate

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `title` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `scope` | string | Si | min. caracteres: 1; max. caracteres: 4000 |

## ProcedureResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `title` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `scope` | string | Si | min. caracteres: 1; max. caracteres: 4000 |
| `id` | string (uuid) | Si | - |
| `organization_id` | string (uuid) | Si | - |
| `created_at` | string (date-time) | Si | - |

## RegisterRequest

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `email` | string (email) | Si | - |
| `password` | string (password) | Si | min. caracteres: 12; max. caracteres: 128 |
| `display_name` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `organization_name` | string | Si | min. caracteres: 1; max. caracteres: 200 |

## SessionCreate

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `objective` | string | Si | min. caracteres: 1; max. caracteres: 4000 |
| `application_name` | string | Si | min. caracteres: 1; max. caracteres: 200 |
| `consent` | boolean | Si | valor obligatorio: true |

## SessionResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `organization_id` | string (uuid) | Si | - |
| `author_id` | string (uuid) | Si | - |
| `objective` | string | Si | - |
| `application_name` | string | Si | - |
| `status` | string | Si | - |
| `consent_at` | string (date-time) | Si | - |
| `created_at` | string (date-time) | Si | - |
| `finished_at` | string (date-time) o null | Si | - |

## StepResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `position` | integer | Si | minimo: 1; maximo: 10000 |
| `instruction` | string | Si | min. caracteres: 1; max. caracteres: 10000 |
| `expected_result` | string | Si | min. caracteres: 1; max. caracteres: 10000 |
| `origin` | string | Si | `observed`, `user_explained`, `inferred` |
| `validation_status` | string | No | defecto: "pending"; `pending`, `confirmed`, `rejected` |
| `id` | string (uuid) | Si | - |
| `version_id` | string (uuid) | Si | - |

## StepWrite

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `position` | integer | Si | minimo: 1; maximo: 10000 |
| `instruction` | string | Si | min. caracteres: 1; max. caracteres: 10000 |
| `expected_result` | string | Si | min. caracteres: 1; max. caracteres: 10000 |
| `origin` | string | Si | `observed`, `user_explained`, `inferred` |
| `validation_status` | string | No | defecto: "pending"; `pending`, `confirmed`, `rejected` |

## TokenResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `access_token` | string | Si | - |
| `token_type` | string | No | defecto: "bearer"; valor obligatorio: "bearer" |
| `expires_at` | string (date-time) | Si | - |

## TutorialResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `version_id` | string (uuid) | Si | - |
| `format` | string | Si | - |
| `content` | string o null | Si | - |
| `created_at` | string (date-time) | Si | - |

## TutorialWrite

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `content` | string | Si | min. caracteres: 1; max. caracteres: 100000 |

## UserResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `email` | string | Si | - |
| `display_name` | string | Si | - |
| `memberships` | lista de MembershipResponse | Si | - |

## ValidationError

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `loc` | lista de string o integer | Si | - |
| `msg` | string | Si | - |
| `type` | string | Si | - |
| `input` | objeto | No | - |
| `ctx` | object | No | - |

## VersionCreate

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `summary` | string | No | max. caracteres: 10000; defecto: "" |
| `source_session_id` | string (uuid) o null | No | - |

## VersionResponse

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `id` | string (uuid) | Si | - |
| `procedure_id` | string (uuid) | Si | - |
| `source_session_id` | string (uuid) o null | Si | - |
| `version_number` | integer | Si | - |
| `status` | string | Si | - |
| `summary` | string | Si | - |
| `reviewer_id` | string (uuid) o null | Si | - |
| `approved_at` | string (date-time) o null | Si | - |
| `published_at` | string (date-time) o null | Si | - |
| `created_at` | string (date-time) | Si | - |
