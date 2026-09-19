-- Requires 015. Change proposals could only ever insert a step. Adds edit and
-- delete: kind picks which, step_position names the existing step an edit or
-- delete targets (insert keeps using after_position, already on the table).
BEGIN;
ALTER TABLE cognitive.change_proposals ADD COLUMN kind text NOT NULL DEFAULT 'insert'
  CHECK (kind IN ('insert', 'edit', 'delete'));
ALTER TABLE cognitive.change_proposals ADD COLUMN step_position integer
  CHECK (step_position IS NULL OR step_position > 0);
INSERT INTO cognitive.schema_migrations(version) VALUES ('018_change_proposal_kinds');
COMMIT;
