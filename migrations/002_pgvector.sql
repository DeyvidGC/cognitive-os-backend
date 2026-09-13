-- Requires pgvector installed on the PostgreSQL server. Run after 001.
BEGIN;
DO $$ BEGIN
  IF current_database() <> 'cognitive' THEN
    RAISE EXCEPTION 'Connect to cognitive before applying this migration';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
    RAISE EXCEPTION 'Install pgvector on the PostgreSQL server first';
  END IF;
END $$;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
CREATE TABLE cognitive.chunk_embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  chunk_id uuid NOT NULL,
  model_name text NOT NULL CHECK (length(trim(model_name)) > 0),
  embedding public.vector(1536) NOT NULL CHECK (public.vector_norm(embedding) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, chunk_id, model_name),
  FOREIGN KEY (organization_id, chunk_id)
    REFERENCES cognitive.knowledge_chunks(organization_id, id)
);
INSERT INTO cognitive.schema_migrations(version) VALUES ('002_pgvector');
COMMIT;
