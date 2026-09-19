-- Requires 002 and 007. Tracks chatbot questions the published knowledge base
-- could not answer. Repeated phrasings of the same unanswered question are
-- deduplicated by embedding similarity instead of growing one row per question.
BEGIN;
CREATE TABLE cognitive.knowledge_gaps (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  question text NOT NULL,
  model_name text NOT NULL,
  embedding public.vector(1536) NOT NULL,
  asked_count integer NOT NULL DEFAULT 1 CHECK (asked_count > 0),
  best_score double precision,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
  created_at timestamptz NOT NULL DEFAULT now(),
  last_asked_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz,
  resolved_by uuid,
  FOREIGN KEY (organization_id, resolved_by) REFERENCES cognitive.memberships(organization_id, user_id)
);
CREATE INDEX knowledge_gaps_tenant_open ON cognitive.knowledge_gaps(organization_id, model_name)
  WHERE status = 'open';
INSERT INTO cognitive.schema_migrations(version) VALUES ('012_knowledge_gaps');
COMMIT;
