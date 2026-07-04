import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_file

OPENAPI_PATH = Path(__file__).resolve().parent.parent / "openapi.json"

logger = logging.getLogger("cloudmart")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
)
logger.addHandler(_handler)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = (
            "no-referrer-strict-origin-when-cross-origin"
        )
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

    @app.route("/", methods=["GET", "POST"])
    def index():
        logger.info(
            "Home page requested", extra={"ip": request.remote_addr or "unknown"}
        )

        name = ""
        if request.method == "POST":
            name = request.form.get("name", "").strip()[:80]

        return app.jinja_env.get_template("index.html").render(name=name)

    @app.route("/about")
    def about():
        return app.jinja_env.get_template("about.html").render()

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.route("/openapi.json")
    def openapi():
        return send_file(OPENAPI_PATH, mimetype="application/json")

    return app
