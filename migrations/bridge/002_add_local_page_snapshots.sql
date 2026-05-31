CREATE TABLE IF NOT EXISTS local_page_snapshots (
    id UUID PRIMARY KEY,
    page_id UUID NOT NULL,
    space_id UUID NOT NULL,
    local_path TEXT NULL,
    content TEXT NOT NULL,
    base_revision_hash TEXT NULL,
    snapshotted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_local_page_snapshots_page_id
    ON local_page_snapshots(page_id);

CREATE INDEX IF NOT EXISTS idx_local_page_snapshots_status
    ON local_page_snapshots(status);
