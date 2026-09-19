-- Requires 014. Adds 'retired' to policy_documents.status so a wrong or
-- obsolete upload can be withdrawn from search and listing without a hard
-- delete -- this codebase has no DELETE endpoints anywhere, by design.
BEGIN;
ALTER TABLE cognitive.policy_documents DROP CONSTRAINT policy_documents_status_check;
ALTER TABLE cognitive.policy_documents ADD CONSTRAINT policy_documents_status_check
  CHECK (status IN ('uploading', 'queued', 'processing', 'ready', 'failed', 'retired'));
INSERT INTO cognitive.schema_migrations(version) VALUES ('017_policy_retire');
COMMIT;
