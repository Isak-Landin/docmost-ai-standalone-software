CREATE TABLE IF NOT EXISTS page_versions (
    id UUID PRIMARY KEY,
    page_id UUID NOT NULL,
    space_id UUID NOT NULL,
    revision_hash TEXT NOT NULL,
    title TEXT NULL,
    content TEXT NOT NULL DEFAULT '',
    slug_id TEXT NULL,
    parent_page_id UUID NULL,
    source TEXT NOT NULL,
    source_write_intent_id UUID NULL,
    remote_updated_at TIMESTAMPTZ NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (page_id, revision_hash)
);

CREATE INDEX IF NOT EXISTS idx_page_versions_space_page ON page_versions (space_id, page_id, created_at DESC);

CREATE TABLE IF NOT EXISTS page_heads (
    page_id UUID PRIMARY KEY,
    space_id UUID NOT NULL,
    current_version_id UUID NULL REFERENCES page_versions(id),
    current_revision_hash TEXT NULL,
    title TEXT NULL,
    content TEXT NOT NULL DEFAULT '',
    slug_id TEXT NULL,
    parent_page_id UUID NULL,
    remote_updated_at TIMESTAMPTZ NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    last_source TEXT NOT NULL,
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_page_heads_space_id ON page_heads (space_id);

CREATE TABLE IF NOT EXISTS write_intents (
    id UUID PRIMARY KEY,
    page_id UUID NULL,
    space_id UUID NOT NULL,
    action TEXT NOT NULL,
    caller_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    expected_base_revision_hash TEXT NULL,
    target_revision_hash TEXT NULL,
    title TEXT NULL,
    content TEXT NULL,
    parent_page_id UUID NULL,
    operation TEXT NULL,
    error_text TEXT NULL,
    remote_page_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_at TIMESTAMPTZ NULL,
    failed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_write_intents_space_status ON write_intents (space_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_write_intents_page_status ON write_intents (page_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS write_receipts (
    id UUID PRIMARY KEY,
    write_intent_id UUID NOT NULL REFERENCES write_intents(id),
    page_id UUID NOT NULL,
    space_id UUID NOT NULL,
    expected_revision_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    expires_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_write_receipts_page_hash_status
    ON write_receipts (page_id, expected_revision_hash, status, created_at DESC);

CREATE TABLE IF NOT EXISTS observer_checkpoints (
    page_id UUID PRIMARY KEY,
    space_id UUID NOT NULL,
    last_seen_remote_updated_at TIMESTAMPTZ NULL,
    last_observed_revision_hash TEXT NULL,
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observer_checkpoints_space_id ON observer_checkpoints (space_id);
