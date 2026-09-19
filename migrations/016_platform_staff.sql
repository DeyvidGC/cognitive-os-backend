-- Requires 001. Marks a user as Inventiva platform staff: the only people who
-- can use /master/* to compare knowledge and usage across every organization,
-- deliberately bypassing the per-organization membership check every other
-- endpoint enforces. Defaults to false; nobody gets this by accident.
BEGIN;
ALTER TABLE cognitive.users ADD COLUMN is_platform_staff boolean NOT NULL DEFAULT false;
INSERT INTO cognitive.schema_migrations(version) VALUES ('016_platform_staff');
COMMIT;
