-- Additive migration; retains all recordings, reports and published versions.
BEGIN;
ALTER TABLE cognitive.learning_sessions ADD COLUMN procedure_id uuid;
ALTER TABLE cognitive.learning_sessions ADD CONSTRAINT learning_sessions_procedure_fk
  FOREIGN KEY (organization_id, procedure_id) REFERENCES cognitive.procedures(organization_id, id);
CREATE INDEX learning_sessions_procedure_idx ON cognitive.learning_sessions(organization_id, procedure_id);
ALTER TABLE cognitive.recordings ADD COLUMN title text NOT NULL DEFAULT '';
ALTER TABLE cognitive.recordings ADD COLUMN origin text NOT NULL DEFAULT 'screen_capture'
  CHECK (origin IN ('screen_capture', 'upload'));
CREATE INDEX recordings_history_idx ON cognitive.recordings(organization_id, created_at DESC, id DESC);
INSERT INTO cognitive.schema_migrations(version) VALUES ('009_periodic_learning');
COMMIT;
