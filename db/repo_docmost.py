from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session


# --------------------------------------------------------
# Spaces
# --------------------------------------------------------

def list_spaces(db: Session) -> List[Dict]:
    """
    Returns all non-deleted spaces.
    """
    result = db.execute(
        text("""
            SELECT id, name, slug
            FROM spaces
            WHERE deleted_at IS NULL
            ORDER BY created_at ASC, id ASC
        """)
    )

    return [dict(row._mapping) for row in result]


# --------------------------------------------------------
# Pages for space
# --------------------------------------------------------

def list_pages_for_space(db: Session, space_id: str) -> List[Dict]:
    """
    Returns flat page list for a space.
    Deterministic ordering enforced.
    """
    result = db.execute(
        text("""
            SELECT id, title, parent_page_id, created_at
            FROM pages
            WHERE space_id = :space_id
              AND deleted_at IS NULL
            ORDER BY created_at ASC, id ASC
        """),
        {"space_id": space_id},
    )

    return [dict(row._mapping) for row in result]


# --------------------------------------------------------
# Assist page fetch + validation
# --------------------------------------------------------

def get_pages_for_assist(
    db: Session,
    space_id: str,
    page_ids: List[str],
) -> List[Dict]:
    """
    Validates that all page_ids belong to space_id and are not deleted.
    Returns id, title, text_content.
    Raises ValueError if mismatch.
    """

    result = db.execute(
        text("""
            SELECT id, title, text_content
            FROM pages
            WHERE id = ANY(:page_ids)
              AND space_id = :space_id
              AND deleted_at IS NULL
            ORDER BY created_at ASC, id ASC
        """),
        {
            "page_ids": page_ids,
            "space_id": space_id,
        },
    )

    rows = [dict(row._mapping) for row in result]

    if len(rows) != len(page_ids):
        raise ValueError("One or more pages are invalid or do not belong to the space")

    return rows
