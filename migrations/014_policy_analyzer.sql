-- Requires 002 and 013. Policy documents get their own small status machine
-- (uploading -> queued -> processing -> ready/failed) instead of the shared
-- cognitive.jobs table, which requires a session_id or version_id per row.
-- policy_documents intentionally shares the blob_key/blob_snapshot/media_type/
-- size_bytes/content_sha256 shape of cognitive.recordings so the existing
-- AzureRecordingStore transfer/freeze/download logic works on it unchanged.
BEGIN;
CREATE TABLE cognitive.policy_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  blob_key text NOT NULL,
  blob_snapshot text,
  media_type text NOT NULL DEFAULT 'application/pdf' CHECK (media_type = 'application/pdf'),
  title text NOT NULL DEFAULT '',
  source text NOT NULL CHECK (source IN ('upload', 'sync')),
  size_bytes bigint NOT NULL CHECK (size_bytes > 0),
  content_sha256 text CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[a-f0-9]{64}$'),
  status text NOT NULL DEFAULT 'uploading'
    CHECK (status IN ('uploading', 'queued', 'processing', 'ready', 'failed')),
  error_code text,
  model_name text,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  locked_until timestamptz,
  locked_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  analyzed_at timestamptz,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, blob_key),
  CHECK (status = 'uploading' OR blob_snapshot IS NOT NULL)
);
CREATE INDEX policy_documents_queue ON cognitive.policy_documents(organization_id)
  WHERE status = 'queued';
CREATE TABLE cognitive.policy_vectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  policy_id uuid NOT NULL,
  position integer NOT NULL CHECK (position >= 0),
  content text NOT NULL,
  source jsonb NOT NULL,
  model_name text NOT NULL,
  embedding public.vector(1536) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, policy_id) REFERENCES cognitive.policy_documents(organization_id, id),
  UNIQUE (organization_id, policy_id, position, model_name)
);
CREATE INDEX policy_vectors_tenant ON cognitive.policy_vectors(organization_id, model_name);
ALTER TABLE cognitive.chat_queries ADD COLUMN policy_id uuid;
INSERT INTO cognitive.schema_migrations(version) VALUES ('014_policy_analyzer');
COMMIT;
