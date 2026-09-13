# Diccionario de tablas

[Estructura](01-estructura.md) | [Indice](../README.md)

Resumen funcional del esquema cognitive al 2026-09-13. Se destacan campos y
restricciones relevantes; consultar las migraciones para el DDL completo.
PK es clave primaria y FK referencia a otra tabla. created_at normalmente usa now().

| Tabla | Para que existe | Campos y relaciones principales |
| --- | --- | --- |
| schema_migrations | Saber que SQL se aplico | version PK, applied_at |
| organizations | Equipo o cliente propietario | id UUID PK, name no vacio, created_at |
| users | Identidad del producto | id PK, identity_subject unico, display_name; las cuentas locales usan prefijo local: |
| memberships | Unir usuarios con organizaciones y roles | PK (organization_id, user_id); role owner/author/reviewer/reader; FK a ambas entidades |
| local_credentials | Login con correo/contrasena | user_id PK/FK, email unico en minusculas, password_hash Argon2, failed_attempts, locked_until |
| auth_tokens | Sesiones de autenticacion revocables | token_hash PK hexadecimal de 64 caracteres, user_id FK, created_at, expires_at, revoked_at; caducidad posterior a creacion |
| learning_sessions | Captura de la explicacion del experto | id PK, organization_id, author_id vinculado a memberships, objective, application_name, status, consent_at, finished_at |
| session_events | Linea temporal de mensajes o eventos | id PK, session_id, sequence_number, idempotency_key, event_type, offset_ms, payload JSONB, evidence_id opcional |
| evidence | Referencia de una captura | id PK, session_id, storage_key unico, media_type, sha256 de 64 caracteres, size_bytes, captured_at |
| clarifications | Dudas planteadas al experto | id PK, session_id, question, answer, answered_by FK a membresia, resolved_at; resolver exige respuesta y usuario |
| procedures | Identidad estable del proceso | id PK, organization_id, title no vacio, scope |
| procedure_versions | Version concreta y estado editorial | id PK, procedure_id, source_session_id opcional, version_number, status, summary, model_name/prompt_version opcionales, reviewer_id, approved_at, published_at |
| steps | Acciones ordenadas de una version | id PK, version_id, position, instruction, expected_result, origin, validation_status |
| decisions | Condiciones y ramificaciones de pasos | id PK, version_id, step_id, condition, action, next_step_id opcional de la misma version; sin endpoints de edicion aun |
| step_evidence | Relacion muchos-a-muchos entre pasos y capturas | PK (organization_id, step_id, evidence_id), explanation; referencias de la misma organizacion |
| knowledge_chunks | Texto que se puede recuperar | id PK, version_id, step_id opcional, position, content no vacio, search_document generado con to_tsvector en espanol |
| tutorials | Presentacion de una version | id PK, version_id, format, content o storage_key; unico por organizacion/version/formato; API usa Markdown |
| jobs | Trabajo pendiente y control de ejecucion | id PK, organization_id, session_id/version_id opcionales pero al menos uno requerido, kind, status, idempotency_key, attempts, max_attempts, available_at, locked_until, locked_by, last_error, completed_at |
| audit_events | Historial de operaciones | id PK, organization_id, actor_id opcional, action, resource_type, resource_id, details JSONB; API registra operaciones editoriales |

## Reglas que evitan datos incoherentes

session_events tiene UNIQUE por sesion/secuencia y por sesion/idempotency_key.
Si referencia una evidencia, esta debe pertenecer a la misma sesion y organizacion.
Los endpoints actuales solo aceptan mensajes/transcripciones; el SQL tambien admite
capture, clarification y system para futuras integraciones.

procedure_versions es unica por organizacion/procedimiento/numero; un indice parcial
permite solo una version published. approved/published exige revisor y fecha de
aprobacion; published exige fecha de publicacion. Los pasos son unicos por posicion
en cada version; la API exige posiciones consecutivas antes de revision.

El SQL admite formatos markdown/html/video para tutorials; la API actual solo
escribe Markdown. knowledge_chunks es unico por version/posicion y enlaza su paso
cuando existe. No guarda embeddings.

Un job running exige locked_until y locked_by. Existen indices para trabajos
pending y leases vencidos. La reserva atomica de cierre ya funciona; aun no hay
un consumidor que reclame jobs. last_error no se devuelve al cliente por /jobs.

audit_events.resource_id es una referencia generica, no una FK a todas las tablas.
Su actor referencia users, no una membresia compuesta. La API debe garantizar el
contexto correcto; no atribuirle una restriccion que no existe en el SQL.

## Tabla vectorial futura

chunk_embeddings se creara al aplicar 002_pgvector. Tendra id, organization_id,
chunk_id, model_name, embedding vector(1536) y created_at. La clave compuesta
referencia knowledge_chunks y hay UNIQUE por organizacion/fragmento/modelo.
El vector debe tener norma positiva. Este campo no equivale a JSON, a una imagen
ni a un hash de contrasena.

## Indices relevantes

| Indice | Utilidad |
| --- | --- |
| one_published_version | Impedir dos publicaciones vigentes del mismo procedimiento |
| knowledge_text_search (GIN) | Acelerar busqueda textual sobre search_document |
| jobs_pending / jobs_expired | Seleccionar trabajo listo o con lease vencido |
| audit_by_resource | Consultar cambios de un recurso |
| auth_tokens_user / auth_tokens_expiry | Consultar tokens de cuenta y por caducidad |

PK y UNIQUE tambien crean sus indices. No hay un indice HNSW aplicado por la
migracion 002: empieza con busqueda exacta. Los modelos ORM solo mapean las tablas
usadas por esta entrega; no generan estas restricciones durante el arranque.
