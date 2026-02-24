import os
from flask import Flask

from backend.http.routes import register_routes
from logging_config import setup_logging
setup_logging(_service="backend")


def create_app() -> Flask:
    app = Flask(__name__)
    register_routes(app)
    return app


if __name__ == "__main__":
    host = os.getenv("BACKEND_LISTEN_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_LISTEN_PORT", "8100"))
    create_app().run(host=host, port=port, threaded=True)
