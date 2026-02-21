import os
from typing import Any, Dict, Optional
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify

DB_HOST = os.getenv("DOCMOST_DB_HOST", "db")
DB_PORT = int(os.getenv("DOCMOST_DB_PORT", "5432"))
DB_NAME = os.getenv("DOCMOST_DB_NAME", "docmost")
DB_USER = os.getenv("DOCMOST_DB_USER", "docmost")
DB_PASS = os.getenv("DOCMOST_DB_PASSWORD", "STRONG_DB_PASSWORD")

LISTEN_HOST = os.getenv("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "8099"))

app = Flask(__name__)

"""
# TODO - This is the get_pages_content function - DONE
def run_for_all_pages_content(_space_id):
    pass

# TODO
def run_for_pages_by_space():
    pass

# TODO
def run_for_space():
    pass

# TODO
def run_for_all_spaces():
    pass
"""


if __name__ == "__main__":
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)
