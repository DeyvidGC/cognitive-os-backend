-- Additive migration; retains all recordings, reports and published versions.
-- Adds live bidirectional-voice session tracking and a dedicated transcript event type
-- for the realtime voice agent, separate from client-submitted 'transcript' events.
BEGIN;
CREATE TABLE cognitive.realtime_voice_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  session_id uuid NOT NULL,
  user_id uuid NOT NULL,
  model text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ended', 'failed')),
  ended_reason text CHECK (ended_reason IS NULL OR ended_reason IN
    ('client_disconnect', 'session_status_changed', 'max_duration', 'error')),
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at timestamptz,
  transcript_event_count integer NOT NULL DEFAULT 0 CHECK (transcript_event_count >= 0),
  clarifications_created integer NOT NULL DEFAULT 0 CHECK (clarifications_created >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (status != 'active' OR ended_at IS NULL),
  CHECK (status = 'active' OR ended_at IS NOT NULL),
  FOREIGN KEY (organization_id, session_id) REFERENCES cognitive.learning_sessions(organization_id, id),
  FOREIGN KEY (organization_id, user_id) REFERENCES cognitive.memberships(organization_id, user_id)
);
-- Enforces one active realtime voice session per learning session.
CREATE UNIQUE INDEX realtime_voice_sessions_active_idx
  ON cognitive.realtime_voice_sessions(organization_id, session_id) WHERE status = 'active';
CREATE INDEX realtime_voice_sessions_history_idx
  ON cognitive.realtime_voice_sessions(organization_id, session_id, started_at DESC);

ALTER TABLE cognitive.session_events DROP CONSTRAINT session_events_event_type_check;
ALTER TABLE cognitive.session_events ADD CONSTRAINT session_events_event_type_check
  CHECK (event_type IN ('message', 'capture', 'transcript', 'clarification', 'system', 'realtime_voice_transcript'));

INSERT INTO cognitive.schema_migrations(version) VALUES ('010_realtime_voice');
COMMIT;
