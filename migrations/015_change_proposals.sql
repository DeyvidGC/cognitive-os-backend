-- Requires 001. A natural-language edit request against a published version,
-- reviewed by a human before it becomes a new draft version. Applying never
-- mutates the published version in place; it creates version_number+1 as a
-- normal draft that still has to go through submit/approve/publish.
BEGIN;
CREATE TABLE cognitive.change_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  version_id uuid NOT NULL,
  procedure_id uuid NOT NULL,
  requested_by uuid NOT NULL,
  request_text text NOT NULL,
  after_position integer NOT NULL CHECK (after_position >= 0),
  instruction text NOT NULL,
  expected_result text NOT NULL,
  rationale text NOT NULL DEFAULT '',
  model_name text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'applied', 'discarded')),
  applied_version_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  resolved_by uuid,
  FOREIGN KEY (organization_id, version_id) REFERENCES cognitive.procedure_versions(organization_id, id),
  FOREIGN KEY (organization_id, procedure_id) REFERENCES cognitive.procedures(organization_id, id),
  FOREIGN KEY (organization_id, requested_by) REFERENCES cognitive.memberships(organization_id, user_id),
  FOREIGN KEY (organization_id, resolved_by) REFERENCES cognitive.memberships(organization_id, user_id),
  FOREIGN KEY (organization_id, applied_version_id) REFERENCES cognitive.procedure_versions(organization_id, id)
);
CREATE INDEX change_proposals_pending ON cognitive.change_proposals(organization_id, version_id)
  WHERE status = 'pending';
INSERT INTO cognitive.schema_migrations(version) VALUES ('015_change_proposals');
COMMIT;
