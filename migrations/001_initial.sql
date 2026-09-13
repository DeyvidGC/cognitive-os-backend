-- Cognitive OS: initial schema. Run once against cognitive.
BEGIN;
DO $$ BEGIN
  IF current_database() <> 'cognitive' THEN
    RAISE EXCEPTION 'Connect to cognitive before applying this migration';
  END IF;
END $$;
CREATE SCHEMA cognitive;
SET LOCAL search_path TO cognitive, public;

CREATE TABLE schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_subject text NOT NULL UNIQUE,
  display_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE memberships (
  organization_id uuid NOT NULL REFERENCES organizations(id),
  user_id uuid NOT NULL REFERENCES users(id),
  role text NOT NULL CHECK (role IN ('owner','author','reviewer','reader')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, user_id)
);
CREATE TABLE learning_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  author_id uuid NOT NULL,
  objective text NOT NULL CHECK (length(trim(objective)) > 0),
  application_name text NOT NULL,
  status text NOT NULL DEFAULT 'capturing'
    CHECK (status IN ('capturing','processing','completed','failed')),
  consent_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  UNIQUE (organization_id, id),
  FOREIGN KEY (organization_id, author_id) REFERENCES memberships(organization_id, user_id),
  CHECK (finished_at IS NULL OR finished_at >= created_at)
);
CREATE TABLE evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  session_id uuid NOT NULL,
  storage_key text NOT NULL UNIQUE,
  media_type text NOT NULL,
  sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$'),
  size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
  captured_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, session_id, id),
  FOREIGN KEY (organization_id, session_id) REFERENCES learning_sessions(organization_id, id)
);
CREATE TABLE session_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  session_id uuid NOT NULL,
  sequence_number bigint NOT NULL CHECK (sequence_number >= 0),
  idempotency_key text NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('message','capture','transcript','clarification','system')),
  offset_ms bigint NOT NULL CHECK (offset_ms >= 0),
  payload jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(payload) = 'object'),
  evidence_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, session_id, sequence_number),
  UNIQUE (organization_id, session_id, idempotency_key),
  FOREIGN KEY (organization_id, session_id) REFERENCES learning_sessions(organization_id, id),
  FOREIGN KEY (organization_id, session_id, evidence_id) REFERENCES evidence(organization_id, session_id, id)
);
CREATE TABLE procedures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  title text NOT NULL CHECK (length(trim(title)) > 0),
  scope text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);
CREATE TABLE procedure_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  procedure_id uuid NOT NULL,
  source_session_id uuid,
  version_number integer NOT NULL CHECK (version_number > 0),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','in_review','approved','published','retired')),
  summary text NOT NULL DEFAULT '',
  model_name text,
  prompt_version text,
  reviewer_id uuid,
  approved_at timestamptz,
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, procedure_id, version_number),
  FOREIGN KEY (organization_id, procedure_id) REFERENCES procedures(organization_id, id),
  FOREIGN KEY (organization_id, source_session_id) REFERENCES learning_sessions(organization_id, id),
  FOREIGN KEY (organization_id, reviewer_id) REFERENCES memberships(organization_id, user_id),
  CHECK (status NOT IN ('approved','published') OR (reviewer_id IS NOT NULL AND approved_at IS NOT NULL)),
  CHECK (status <> 'published' OR published_at IS NOT NULL)
);
CREATE UNIQUE INDEX one_published_version ON procedure_versions(organization_id, procedure_id)
  WHERE status = 'published';
CREATE TABLE steps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  version_id uuid NOT NULL,
  position integer NOT NULL CHECK (position > 0),
  instruction text NOT NULL CHECK (length(trim(instruction)) > 0),
  expected_result text NOT NULL,
  origin text NOT NULL CHECK (origin IN ('observed','user_explained','inferred')),
  validation_status text NOT NULL DEFAULT 'pending'
    CHECK (validation_status IN ('pending','confirmed','rejected')),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, version_id, id),
  UNIQUE (organization_id, version_id, position),
  FOREIGN KEY (organization_id, version_id) REFERENCES procedure_versions(organization_id, id)
);
CREATE TABLE decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  version_id uuid NOT NULL,
  step_id uuid NOT NULL,
  condition text NOT NULL,
  action text NOT NULL,
  next_step_id uuid,
  FOREIGN KEY (organization_id, version_id, step_id) REFERENCES steps(organization_id, version_id, id),
  FOREIGN KEY (organization_id, version_id, next_step_id) REFERENCES steps(organization_id, version_id, id)
);
CREATE TABLE step_evidence (
  organization_id uuid NOT NULL,
  step_id uuid NOT NULL,
  evidence_id uuid NOT NULL,
  explanation text NOT NULL DEFAULT '',
  PRIMARY KEY (organization_id, step_id, evidence_id),
  FOREIGN KEY (organization_id, step_id) REFERENCES steps(organization_id, id),
  FOREIGN KEY (organization_id, evidence_id) REFERENCES evidence(organization_id, id)
);
CREATE TABLE clarifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  session_id uuid NOT NULL,
  question text NOT NULL,
  answer text,
  answered_by uuid,
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, session_id) REFERENCES learning_sessions(organization_id, id),
  FOREIGN KEY (organization_id, answered_by) REFERENCES memberships(organization_id, user_id),
  CHECK (resolved_at IS NULL OR (answer IS NOT NULL AND answered_by IS NOT NULL))
);
CREATE TABLE knowledge_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  version_id uuid NOT NULL,
  step_id uuid,
  position integer NOT NULL CHECK (position >= 0),
  content text NOT NULL CHECK (length(trim(content)) > 0),
  search_document tsvector GENERATED ALWAYS AS (to_tsvector('spanish'::regconfig, content)) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, version_id, position),
  FOREIGN KEY (organization_id, version_id) REFERENCES procedure_versions(organization_id, id),
  FOREIGN KEY (organization_id, version_id, step_id) REFERENCES steps(organization_id, version_id, id)
);
CREATE INDEX knowledge_text_search ON knowledge_chunks USING gin(search_document);
CREATE TABLE tutorials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  version_id uuid NOT NULL,
  format text NOT NULL CHECK (format IN ('markdown','html','video')),
  content text,
  storage_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, version_id, format),
  FOREIGN KEY (organization_id, version_id) REFERENCES procedure_versions(organization_id, id),
  CHECK (content IS NOT NULL OR storage_key IS NOT NULL)
);
CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  session_id uuid,
  version_id uuid,
  kind text NOT NULL CHECK (kind IN ('consolidate','generate_tutorial','index_knowledge')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
  idempotency_key text NOT NULL,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
  available_at timestamptz NOT NULL DEFAULT now(),
  locked_until timestamptz,
  locked_by text,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE (organization_id, idempotency_key),
  FOREIGN KEY (organization_id, session_id) REFERENCES learning_sessions(organization_id, id),
  FOREIGN KEY (organization_id, version_id) REFERENCES procedure_versions(organization_id, id),
  CHECK (session_id IS NOT NULL OR version_id IS NOT NULL),
  CHECK (status <> 'running' OR (locked_until IS NOT NULL AND locked_by IS NOT NULL))
);
CREATE INDEX jobs_pending ON jobs(available_at) WHERE status = 'pending';
CREATE INDEX jobs_expired ON jobs(locked_until) WHERE status = 'running';
CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id),
  actor_id uuid REFERENCES users(id),
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id uuid NOT NULL,
  details jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(details) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_by_resource ON audit_events(organization_id, resource_type, resource_id, created_at);
INSERT INTO schema_migrations(version) VALUES ('001_initial');
COMMIT;

