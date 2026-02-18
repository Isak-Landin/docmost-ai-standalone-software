from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from psycopg2.extras import RealDictCursor

from .session import get_conn


JOB_TABLE = "public.dah_jobs"


@dataclass(frozen=True)
class JobRow:
    id: UUID
    status: str
    space_id: Optional[UUID]
    selected_page_ids: List[UUID]
    message: str
    final_text: Optional[str]
    error_text: Optional[str]
    created_at: Optional[str]  # ISO-ish string from DB driver, used only for ordering/visibility


def ensure_schema() -> None:
    """
    Creates the single MVP table if missing.
    This keeps schema in the repo layer (SQL-only rule).
    """
    sql = f"""
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS {JOB_TABLE} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        status TEXT NOT NULL,
        space_id UUID NULL,
        selected_page_ids UUID[] NOT NULL DEFAULT '{{}}'::uuid[],
        message TEXT NOT NULL,

        final_text TEXT NULL,
        error_text TEXT NULL,

        -- Not exposed as a product feature, but required for deterministic "oldest first".
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS dah_jobs_status_created_idx
      ON {JOB_TABLE} (status, created_at);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def create_job(*, status: str, space_id: Optional[UUID], selected_page_ids: List[UUID], message: str) -> UUID:
    sql = f"""
    INSERT INTO {JOB_TABLE} (status, space_id, selected_page_ids, message)
    VALUES (%(status)s, %(space_id)s, %(selected_page_ids)s, %(message)s)
    RETURNING id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "status": status,
                    "space_id": str(space_id) if space_id else None,
                    "selected_page_ids": [str(x) for x in selected_page_ids],
                    "message": message,
                },
            )
            row = cur.fetchone()
            return row[0]


def claim_next_job(*, from_status: str, to_status: str) -> Optional[JobRow]:
    """
    Oldest-first claim using created_at.
    Concurrency=1 for MVP, but this still uses SKIP LOCKED to be safe if later increased.
    """
    sql = f"""
    WITH picked AS (
        SELECT id
        FROM {JOB_TABLE}
        WHERE status = %(from_status)s
        ORDER BY created_at ASC
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE {JOB_TABLE} j
    SET status = %(to_status)s
    FROM picked
    WHERE j.id = picked.id
    RETURNING j.id, j.status, j.space_id, j.selected_page_ids, j.message, j.final_text, j.error_text, j.created_at
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, {"from_status": from_status, "to_status": to_status})
            r = cur.fetchone()
            if not r:
                return None
            return _row_to_job(r)


def set_job_done(*, job_id: UUID, status: str, final_text: str) -> None:
    sql = f"""
    UPDATE {JOB_TABLE}
    SET status = %(status)s,
        final_text = %(final_text)s,
        error_text = NULL
    WHERE id = %(id)s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": str(job_id), "status": status, "final_text": final_text})


def set_job_failed(*, job_id: UUID, status: str, error_text: str) -> None:
    sql = f"""
    UPDATE {JOB_TABLE}
    SET status = %(status)s,
        error_text = %(error_text)s
    WHERE id = %(id)s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": str(job_id), "status": status, "error_text": error_text})


def get_job(*, job_id: UUID) -> Optional[JobRow]:
    sql = f"""
    SELECT id, status, space_id, selected_page_ids, message, final_text, error_text, created_at
    FROM {JOB_TABLE}
    WHERE id = %(id)s
    LIMIT 1
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, {"id": str(job_id)})
            r = cur.fetchone()
            if not r:
                return None
            return _row_to_job(r)


def _row_to_job(r: Dict[str, Any]) -> JobRow:
    return JobRow(
        id=UUID(str(r["id"])),
        status=str(r["status"]),
        space_id=UUID(str(r["space_id"])) if r.get("space_id") else None,
        selected_page_ids=[UUID(str(x)) for x in (r.get("selected_page_ids") or [])],
        message=str(r.get("message") or ""),
        final_text=r.get("final_text"),
        error_text=r.get("error_text"),
        created_at=r["created_at"].isoformat() if r.get("created_at") else None,
    )


"""
API specific fetch to allow displaying or usage of space.
Two known use cases, one being passing no id and displaying all spaces on root page.
Other being fetching with id to find space name
"""
def get_space(space_id):
    sql = """
        SELECT *
        FROM spaces WHERE id = %(id)s
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC \
    """

    if not space_id:
        sql = """
              SELECT id, name, slug
              FROM public.spaces
              WHERE deleted_at IS NULL
              ORDER BY created_at ASC, id ASC \
        """


    with get_conn as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if space_id:
                r = cur.fetchone()
                if not r:
                    return None

            if not space_id:
                rs = cur.fetchall() or []
                if not rs or rs == []:
                    return []

                spaces = [
                    {"id": str(r["id"]), "name": r.get("name") or "", "slug": r.get("slug") or ""}
                    for r in rs
                ]
                return spaces
            return []

