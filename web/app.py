from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parents[1]
NEXT_STEPS_PATH = BASE_DIR / "data/next_steps.json"

app = Flask(__name__)


def load_next_steps() -> Dict[str, Any]:
    if not NEXT_STEPS_PATH.exists():
        return {"generated": None, "items": []}
    return json.loads(NEXT_STEPS_PATH.read_text())


@app.route("/")
def index() -> str:
    payload = load_next_steps()
    return render_template("index.html", generated=payload.get("generated"), items=payload.get("items", []))


@app.route("/api/next-steps")
def api_next_steps():
    return jsonify(load_next_steps())


@app.route("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
