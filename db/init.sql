-- db/init.sql
-- Creates DAH MVP tables: doc_ai_job + doc_ai_requests

-- 1) UUID generator (use gen_random_uuid())
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2) Status enum
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'doc_ai_job_status') THEN
    CREATE TYPE doc_ai_job_status AS ENUM ('created', 'processing', 'completed', 'failed');
  END IF;
END $$;

-- 3) doc_ai_job
-- seq is the deterministic, monotonic job identifier used by API/UI
CREATE TABLE IF NOT EXISTS doc_ai_job (
  id         uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  seq        integer           GENERATED ALWAYS AS IDENTITY UNIQUE NOT NULL,
  status     doc_ai_job_status NOT NULL DEFAULT 'created',
  created_at timestamptz       NOT NULL DEFAULT now(),
  updated_at timestamptz       NOT NULL DEFAULT now()
);

-- Keep updated_at fresh
CREATE OR REPLACE FUNCTION dah_touch_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_doc_ai_job_touch ON doc_ai_job;
CREATE TRIGGER trg_doc_ai_job_touch
BEFORE UPDATE ON doc_ai_job
FOR EACH ROW
EXECUTE FUNCTION dah_touch_updated_at();

-- 4) doc_ai_requests
-- Stores only completed model output + the inputs you chose to persist.
CREATE TABLE IF NOT EXISTS doc_ai_requests (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  job_seq     integer     NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),

  space_id    uuid        NOT NULL,
  page_ids    uuid[]      NOT NULL,
  page_title  text[]      NOT NULL, -- aligned index-wise with page_ids

  user_prompt  text       NOT NULL, -- empty string allowed
  model_output text       NOT NULL,
  model_name   text       NULL,

  CONSTRAINT fk_doc_ai_requests_job_seq
    FOREIGN KEY (job_seq) REFERENCES doc_ai_job(seq)
    ON DELETE RESTRICT,

  CONSTRAINT chk_page_ids_not_empty
    CHECK (array_length(page_ids, 1) IS NOT NULL AND array_length(page_ids, 1) > 0),

  CONSTRAINT chk_page_title_matches_page_ids
    CHECK (array_length(page_ids, 1) = array_length(page_title, 1))
);

CREATE INDEX IF NOT EXISTS idx_doc_ai_job_status_seq
  ON doc_ai_job (status, seq);

CREATE INDEX IF NOT EXISTS idx_doc_ai_requests_job_seq
  ON doc_ai_requests (job_seq);

CREATE INDEX IF NOT EXISTS idx_doc_ai_requests_space_created
  ON doc_ai_requests (space_id, created_at DESC);
