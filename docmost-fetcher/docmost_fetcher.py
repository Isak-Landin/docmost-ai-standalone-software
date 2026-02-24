import os
from typing import Any, Dict

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from api.routes import docmost_api
from logging_config import setup_logging
setup_logging(_service="docmost-fetcher")


LISTEN_HOST = os.getenv("UI_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("UI_LISTEN_PORT", "8099"))

DOCMOST_FETCHER_API = os.getenv("DOCMOST_FETCHER_API", "/docmost/api")

app = Flask(__name__)

app.register_blueprint(docmost_api)

if __name__ == "__main__":
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)
