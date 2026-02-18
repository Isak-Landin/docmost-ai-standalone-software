import os
from typing import Any, Dict
import requests

from flask import Flask, jsonify, request, send_from_directory

BACKEND_URL = os.getenv("BACKEND_BASE_URL", "http://backend:8100")
DOCMOST_FETCHER_BASE_URL = os.getenv("DOCMOST_BASE_URL", "http://docmost:8099")
docmost_fetcher_spaces_endpoint = DOCMOST_FETCHER_BASE_URL + os.getenv("SPACES_PATH", "/api/spaces")

UI_LISTEN_HOST = os.getenv("UI_LISTEN_HOST", "0.0.0.0")
UI_LISTEN_PORT = int(os.getenv("UI_LISTEN_PORT", "8090"))

app = Flask(__name__, static_folder="static", static_url_path="/static")


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/api/chat")
def api_chat():
    # Placeholder: wire to your model workflow later.
    data = request.get_json(silent=True) or {}
    return jsonify(
        {
            "ok": True,
            "reply": "CHAT BACKEND NOT IMPLEMENTED YET",
            "echo": {
                "space": data.get("space"),
                "selected_pages": data.get("selected_pages", []),
                "message": data.get("message", ""),
            },
        }
    )

@app.get("/api/spaces")
def api_spaces():
    all_spaces = requests.get(docmost_fetcher_spaces_endpoint).json()

    return jsonify(all_spaces)


if __name__ == "__main__":
    app.run(host=UI_LISTEN_HOST, port=UI_LISTEN_PORT)
