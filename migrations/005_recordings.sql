-- Requires 001 and 004; independent of pgvector. No existing data is removed.
BEGIN;
CREATE TABLE cognitive.recordings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  session_id uuid NOT NULL,
  idempotency_key text NOT NULL,
  blob_key text NOT NULL UNIQUE,
  blob_snapshot text,
  media_type text NOT NULL CHECK (media_type IN ('video/webm','video/mp4')),
  size_bytes bigint NOT NULL CHECK (size_bytes > 0),
  status text NOT NULL DEFAULT 'uploading'
    CHECK (status IN ('uploading','uploaded','queued','processing','ready','failed')),
  consent_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  uploaded_at timestamptz,
  error_code text,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, session_id),
  UNIQUE (organization_id, session_id, id),
  UNIQUE (organization_id, idempotency_key),
  FOREIGN KEY (organization_id, session_id) REFERENCES cognitive.learning_sessions(organization_id,id),
  CHECK (status = 'uploading' OR blob_snapshot IS NOT NULL)
);
CREATE TABLE cognitive.recording_reports (
  recording_id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  content jsonb NOT NULL,
  original_content jsonb NOT NULL,
  sampling jsonb NOT NULL,
  model_name text NOT NULL,
  prompt_version text NOT NULL,
  revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  reviewer_id uuid,
  reviewed_at timestamptz,
  feedback text,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, recording_id) REFERENCES cognitive.recordings(organization_id,id),
  FOREIGN KEY (organization_id, reviewer_id) REFERENCES cognitive.memberships(organization_id,user_id),
  CHECK (review_status = 'pending' OR (reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL))
);
ALTER TABLE cognitive.jobs ADD COLUMN recording_id uuid;
ALTER TABLE cognitive.jobs ADD CONSTRAINT jobs_recording_fk
  FOREIGN KEY (organization_id, session_id, recording_id)
  REFERENCES cognitive.recordings(organization_id, session_id, id);
ALTER TABLE cognitive.jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE cognitive.jobs ADD CONSTRAINT jobs_kind_check
  CHECK (kind IN ('consolidate','generate_tutorial','index_knowledge','analyze_recording'));
ALTER TABLE cognitive.jobs ADD CONSTRAINT jobs_recording_kind_check
  CHECK ((kind = 'analyze_recording' AND recording_id IS NOT NULL AND session_id IS NOT NULL)
         OR (kind <> 'analyze_recording' AND recording_id IS NULL));
INSERT INTO cognitive.schema_migrations(version) VALUES ('005_recordings');
COMMIT;
