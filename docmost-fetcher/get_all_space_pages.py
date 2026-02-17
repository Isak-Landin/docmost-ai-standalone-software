def get_all_spaces_pages() -> Dict[str, Any]:
    sql_spaces = """
        SELECT
            id,
            name,
	    
        FROM spaces
        WHERE id = %(page_id)s AND space_id = %(space_id)s
        LIMIT 1
    """
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, {"page_id": page_id, "space_id": space_id})
            row = cur.fetchone()

    if not row:
        return {"ok": False, "error": "not_found"}

    return {
        "ok": True,
        "page": {
            "id": str(row["id"]),
            "space_id": str(row["space_id"]),
            "title": row.get("title"),
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            "deleted_at": row["deleted_at"].isoformat() if row.get("deleted_at") else None,
            "text_content": row.get("text_content") or "",
            "content": row.get("content") or {},
        },
    }
