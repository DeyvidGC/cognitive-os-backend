BEGIN;
ALTER TABLE cognitive.recordings ADD COLUMN content_sha256 text
  CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[a-f0-9]{64}$');
ALTER TABLE cognitive.recordings ADD COLUMN audio_consent boolean NOT NULL DEFAULT false;
ALTER TABLE cognitive.recording_reports ADD COLUMN version_id uuid;
ALTER TABLE cognitive.recording_reports ADD CONSTRAINT report_version_fk
  FOREIGN KEY (organization_id, version_id) REFERENCES cognitive.procedure_versions(organization_id,id);
CREATE TABLE cognitive.recording_report_revisions (
  recording_id uuid NOT NULL REFERENCES cognitive.recordings(id),
  revision integer NOT NULL,
  organization_id uuid NOT NULL,
  snapshot jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (recording_id, revision),
  FOREIGN KEY (organization_id, recording_id) REFERENCES cognitive.recordings(organization_id,id)
);
CREATE TABLE cognitive.step_recording_evidence (
  organization_id uuid NOT NULL,
  step_id uuid PRIMARY KEY,
  recording_id uuid NOT NULL,
  report_revision integer NOT NULL,
  frame_indices jsonb NOT NULL,
  FOREIGN KEY (organization_id, step_id) REFERENCES cognitive.steps(organization_id,id),
  FOREIGN KEY (organization_id, recording_id) REFERENCES cognitive.recordings(organization_id,id)
);
CREATE TABLE cognitive.agent_turns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  session_id uuid NOT NULL,
  user_id uuid NOT NULL,
  client_message_id uuid NOT NULL,
  request_hash text NOT NULL,
  user_text text NOT NULL,
  response jsonb,
  status text NOT NULL CHECK (status IN ('pending','completed','failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  locked_until timestamptz NOT NULL,
  attempt_id uuid NOT NULL,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
  UNIQUE (organization_id, session_id, client_message_id),
  FOREIGN KEY (organization_id, session_id) REFERENCES cognitive.learning_sessions(organization_id,id),
  FOREIGN KEY (organization_id, user_id) REFERENCES cognitive.memberships(organization_id,user_id)
);
CREATE INDEX agent_turns_session ON cognitive.agent_turns(organization_id, session_id, created_at);
INSERT INTO cognitive.schema_migrations(version) VALUES ('006_interactive_learning');
COMMIT;
