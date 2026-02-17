CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.dah_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL,
    space_id UUID NULL,
    selected_page_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
    message TEXT NOT NULL,

    final_text TEXT NULL,
    error_text TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dah_jobs_status_created_idx
  ON public.dah_jobs (status, created_at);
