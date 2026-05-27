from __future__ import annotations

from uuid import UUID, uuid4

from app.bridge.schemas.state import WriteReceiptRecord


def create_write_receipt(
    cur,
    *,
    write_intent_id: UUID,
    page_id: UUID,
    space_id: UUID,
    expected_revision_hash: str,
) -> WriteReceiptRecord:
    cur.execute(
        """
        INSERT INTO write_receipts (
            id,
            write_intent_id,
            page_id,
            space_id,
            expected_revision_hash,
            status,
            expires_at,
            created_at,
            confirmed_at
        )
        VALUES (
            %s, %s, %s, %s, %s, 'pending', NOW() + INTERVAL '5 minutes', NOW(), NULL
        )
        RETURNING *
        """,
        (
            str(uuid4()),
            str(write_intent_id),
            str(page_id),
            str(space_id),
            expected_revision_hash,
        ),
    )
    return _map_write_receipt(cur.fetchone())


def get_pending_write_receipt(cur, *, page_id: UUID, expected_revision_hash: str) -> WriteReceiptRecord | None:
    cur.execute(
        """
        SELECT *
        FROM write_receipts
        WHERE page_id = %s
          AND expected_revision_hash = %s
          AND status = 'pending'
          AND (expires_at IS NULL OR expires_at >= NOW())
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (str(page_id), expected_revision_hash),
    )
    row = cur.fetchone()
    return _map_write_receipt(row) if row else None


def mark_write_receipt_confirmed(cur, receipt_id: UUID) -> WriteReceiptRecord:
    cur.execute(
        """
        UPDATE write_receipts
        SET status = 'confirmed',
            confirmed_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (str(receipt_id),),
    )
    return _map_write_receipt(cur.fetchone())


def mark_write_receipts_confirmed_for_intent(cur, intent_id: UUID) -> None:
    cur.execute(
        """
        UPDATE write_receipts
        SET status = 'confirmed',
            confirmed_at = COALESCE(confirmed_at, NOW())
        WHERE write_intent_id = %s
          AND status != 'confirmed'
        """,
        (str(intent_id),),
    )


def expire_write_receipts_for_intent(cur, intent_id: UUID) -> None:
    cur.execute(
        """
        UPDATE write_receipts
        SET status = 'expired'
        WHERE write_intent_id = %s
          AND status = 'pending'
        """,
        (str(intent_id),),
    )


def expire_write_receipts_for_space(cur, space_id: UUID) -> None:
    cur.execute(
        """
        UPDATE write_receipts
        SET status = 'expired'
        WHERE space_id = %s
          AND status = 'pending'
        """,
        (str(space_id),),
    )


def _map_write_receipt(row: dict) -> WriteReceiptRecord:
    return WriteReceiptRecord(
        id=UUID(str(row["id"])),
        write_intent_id=UUID(str(row["write_intent_id"])),
        page_id=UUID(str(row["page_id"])),
        space_id=UUID(str(row["space_id"])),
        expected_revision_hash=row["expected_revision_hash"],
        status=row["status"],
        expires_at=row.get("expires_at"),
        created_at=row["created_at"],
        confirmed_at=row.get("confirmed_at"),
    )
