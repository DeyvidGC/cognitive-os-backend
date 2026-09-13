-- Run after 001_initial. The vector migration is independent and optional.
BEGIN;
DO $$ BEGIN
  IF current_database() <> 'cognitive' THEN
    RAISE EXCEPTION 'Connect to cognitive before applying this migration';
  END IF;
END $$;
CREATE TABLE cognitive.local_credentials (
  user_id uuid PRIMARY KEY REFERENCES cognitive.users(id),
  email text NOT NULL UNIQUE CHECK (email = lower(email)),
  password_hash text NOT NULL,
  failed_attempts integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
  locked_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE cognitive.auth_tokens (
  token_hash text PRIMARY KEY CHECK (token_hash ~ '^[a-f0-9]{64}$'),
  user_id uuid NOT NULL REFERENCES cognitive.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  CHECK (expires_at > created_at)
);
CREATE INDEX auth_tokens_user ON cognitive.auth_tokens(user_id);
CREATE INDEX auth_tokens_expiry ON cognitive.auth_tokens(expires_at);
INSERT INTO cognitive.schema_migrations(version) VALUES ('004_local_auth');
COMMIT;
