BEGIN;
ALTER TABLE cognitive.jobs ADD COLUMN stage text NOT NULL DEFAULT 'queued';
ALTER TABLE cognitive.jobs ADD COLUMN progress_percent integer NOT NULL DEFAULT 0
  CHECK (progress_percent BETWEEN 0 AND 100);
UPDATE cognitive.jobs SET stage='completed', progress_percent=100 WHERE status='completed';
UPDATE cognitive.jobs SET stage='failed' WHERE status='failed';
INSERT INTO cognitive.schema_migrations(version) VALUES ('008_job_progress');
COMMIT;
