import os

from flask import Blueprint, request, jsonify
import requests

from db_functionality import (
get_spaces, get_pages, get_contents, get_page, get_space, get_content
)

import logging
logger = logging.getLogger(__name__)


docmost_api = Blueprint("docmost_fetcher_api_route", __name__)

# MODE
MODE = os.getenv("MODE", "dev")

# ROUTE ENVS
SPACES_ALL_ENDPOINT = os.getenv("SPACES_ALL_ENDPOINT", "/docmost/api")


if MODE == "prod":
    # SCHEMA FILES ENVS PROD
    #  Ensure base path contains trailing / always.
    SCHEMA_BASE_PATH = os.getenv("SCHEMA_BASE_PATH", "./schemas/")
else:
    SCHEMA_BASE_PATH = os.getenv("SCHEMA_BASE_PATH_DEV", "/home/isakadmin/docmost-ai-standalone-software/schemas/")


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
    """
    returns content
    In the format
    space_id: {
        page_id: {
            ... meta data ...
            text_content: str
        }
    }
    """
    page_id = request.args.get("page_id", "").strip()
    content = get_page(page_id)



@docmost_api.get("/get-content-single")
def http_get_content_single():
    _space_id = request.args.get("space_id", "").strip()
    if not _space_id:
        return jsonify({"message": "No space id found"}), 404
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

    return jsonify({"ok": True, "spaces": _spaces})

# ---------------------------------------- #
# ------------- END OF ROUTES ------------ #
# ---------------------------------------- #
"""
find . -type d \( -path ./.git -o -path ./log -o -path ./public -o -path ./tmp -o -path ./venv -o -path ./.idea \) -prune -o ! -type d -print
"""