import os

from flask import Blueprint, request, jsonify
import requests
from db_functionality import get_spaces

from db_functionality import (
get_spaces, get_pages, get_contents, get_space_id_from_page_id,
get_single_page_content, refactor_content
)

docmost_api = Blueprint("docmost_fetcher_api_route", __name__)

SPACES_ALL_ENDPOINT = os.getenv("SPACES_ALL_ENDPOINT", "/docmost/api")

"""
Used to retrieve space or all spaces.
returns all spaces if no space_id else returns space
"""

SPACES_ENDPOINT = "/spaces"

# ---------------------------------------- #
# ---------------- ROUTES ---------------- #
# ---------------------------------------- #

# General TODO. Insert all existing and new functions form test file into this file. First, after ensuring
# TODO; coherency between expected behavior and functional behavior.


@docmost_api.get("/")
def http_home_list_spaces():
    _get_all_spaces_dict = get_spaces()
    return jsonify(_get_all_spaces_dict)

@docmost_api.get("/get-content")
def http_get_content_specific():
    space_id = request.args.get("space_id", "").strip()
    page_id = request.args.get("page_id", "").strip()
    if not space_id or not page_id:
        return jsonify({"ok": True})
    return jsonify(get_contents(space_id=space_id, page_id=page_id))

@docmost_api.get("/get-content-single")
def http_get_content_single(_space_id):
    _get_space_dict = get_spaces(_space_id)
    _get_pages = get_pages(_get_space_dict)
    _get_content = get_contents(pages_by_space=_get_pages)

    return jsonify(_get_content)



@docmost_api.get("/health")
def health():
    return jsonify({"ok": True})


@docmost_api.route(SPACES_ALL_ENDPOINT, methods=["GET"])
def spaces():
    payload = request.get_json(silent=True) or {}
    space_id = None
    if payload:
        space_id = payload.get("space_id") or None

    _spaces = get_spaces(space_id)

    if not _spaces:
        return jsonify({"message": "No spaces found"}), 404

    return jsonify({"ok": True, "spaces": spaces})

# ---------------------------------------- #
# ------------- END OF ROUTES ------------ #
# ---------------------------------------- #