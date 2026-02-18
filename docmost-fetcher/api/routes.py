import os

from flask import Blueprint, request, jsonify
import requests
from db_functionality import get_spaces

docmost_fetcher_api_route = Blueprint("docmost_fetcher_api_route", __name__)

SPACES_ALL_ENDPOINT = os.getenv("SPACES_ALL_ENDPOINT", "/api/spaces")

"""
Used to retrieve space or all spaces.
returns all spaces if no space_id else returns space
"""

SPACES_ENDPOINT = "/spaces"

@docmost_fetcher_api_route.route(SPACES_ALL_ENDPOINT, methods=["GET"])
def spaces():
    payload = request.get_json(silent=True) or {}
    space_id = None
    if payload:
        space_id = payload.get("space_id") or None

    _spaces = get_spaces(space_id)

    if not _spaces:
        return jsonify({"message": "No spaces found"}), 404

    return jsonify({"ok": True, "spaces": spaces})
