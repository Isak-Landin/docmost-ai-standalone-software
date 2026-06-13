-- Ephemeral tracker of conflicts/deletions the background auto-sync detected during automation.
-- It is NOT part of the reconcile/write/observe pipeline; it is a standalone awareness store the
-- /health MCP surface reads. Entries are cleared ONLY by a model action (health_resolve, or the
-- existing resolve_conflict/confirm_deletion flow) - the server never auto-clears, because it can
-- never know the live local state with certainty.
CREATE TABLE IF NOT EXISTS auto_sync_conflicts (
    id UUID PRIMARY KEY,
    space_id UUID NOT NULL,
    page_id UUID NOT NULL,
    kind TEXT NOT NULL DEFAULT 'conflict',
    reason TEXT NULL,
    title TEXT NULL,
    local_path TEXT NULL,
    base_revision_hash TEXT NULL,
    base_version_id UUID NULL,
    local_version TEXT NULL,
    remote_version TEXT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (space_id, page_id)
);

CREATE INDEX IF NOT EXISTS idx_auto_sync_conflicts_space ON auto_sync_conflicts (space_id);
