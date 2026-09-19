-- Additive migration; lets the knowledge base mark older fragments as superseded
-- instead of only ever growing. Existing rows default to 'active' and are unaffected.
BEGIN;
ALTER TABLE cognitive.recording_vectors ADD COLUMN status text NOT NULL DEFAULT 'active'
  CHECK (status IN ('active', 'superseded'));
ALTER TABLE cognitive.recording_vectors ADD COLUMN superseded_by uuid
  REFERENCES cognitive.recording_vectors(id);
CREATE INDEX recording_vectors_active_idx ON cognitive.recording_vectors(organization_id, model_name)
  WHERE status = 'active';
INSERT INTO cognitive.schema_migrations(version) VALUES ('011_knowledge_consolidation');
COMMIT;
