from flask import Blueprint, request
import requests

docmost_fetcher_api_route = Blueprint("docmost_fetcher_api_route", __name__)

"""
Used to retrieve space or all spaces.
returns all spaces if no space_id else returns space
"""

SPACES_ENDPOINT = "/spaces"

@docmost_fetcher_api_route.route("", methods=["GET"])
def spaces():
    payload = request.get_json(silent=True) or {}
    space_id = None
    if payload:
        space_id = payload.get("space_id") or None

    sql = """
    SELECT id, name
    FROM public.spaces
    WHERE deleted_at IS NULL
    ORDER BY created_at ASC
    """

    if space_id:
        sql = f"""
        SELECT id, name
        FROM public.spaces
        WHERE id = {space_id}
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC
        """

    with _conn() as c:
        with c.cursor() as cur:
            if space_id:
                cur.execute(sql, {"space_id": space_id})
            else:
                cur.execute(sql)
            rows = cur.fetchall()
            if not rows:
                return {"ok": False, "error": "not_found"}

            return jsonify({"ok": True, "spaces": rows})
