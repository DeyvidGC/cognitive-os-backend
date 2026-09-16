-- Requires 002, 005 and 006. Embeddings are derived data, never video storage.
BEGIN;
CREATE TABLE cognitive.recording_vectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  recording_id uuid NOT NULL,
  report_revision integer NOT NULL CHECK (report_revision > 0),
  position integer NOT NULL CHECK (position >= 0),
  content text NOT NULL,
  source jsonb NOT NULL,
  model_name text NOT NULL,
  embedding public.vector(1536) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, recording_id) REFERENCES cognitive.recordings(organization_id,id),
  UNIQUE (organization_id, recording_id, report_revision, position, model_name)
);
CREATE INDEX recording_vectors_tenant ON cognitive.recording_vectors(organization_id, model_name);
ALTER TABLE cognitive.jobs DROP CONSTRAINT jobs_kind_check;
ALTER TABLE cognitive.jobs ADD CONSTRAINT jobs_kind_check
  CHECK (kind IN ('consolidate','generate_tutorial','index_knowledge','analyze_recording','index_recording'));
ALTER TABLE cognitive.jobs DROP CONSTRAINT jobs_recording_kind_check;
ALTER TABLE cognitive.jobs ADD CONSTRAINT jobs_recording_kind_check
  CHECK ((kind IN ('analyze_recording','index_recording') AND recording_id IS NOT NULL AND session_id IS NOT NULL)
    OR (kind NOT IN ('analyze_recording','index_recording') AND recording_id IS NULL));
INSERT INTO cognitive.schema_migrations(version) VALUES ('007_recording_vectors');
COMMIT;
