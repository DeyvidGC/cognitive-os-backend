-- Requires 001 and 012. Logs every chatbot question (answered or not) so the
-- usage dashboard can compute counts, daily volume and top topics without
-- re-deriving them from knowledge_gaps, which only tracks unanswered ones.
BEGIN;
CREATE TABLE cognitive.chat_queries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  user_id uuid NOT NULL,
  question text NOT NULL,
  answered boolean NOT NULL,
  session_objective text,
  recording_id uuid,
  gap_id uuid,
  model_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (organization_id, user_id) REFERENCES cognitive.memberships(organization_id, user_id)
);
CREATE INDEX chat_queries_tenant_time ON cognitive.chat_queries(organization_id, created_at);
INSERT INTO cognitive.schema_migrations(version) VALUES ('013_chat_queries');
COMMIT;
