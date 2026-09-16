"""Newton — Data Validation Agent. Flask API plus the built React frontend."""
from __future__ import annotations

import hashlib
import os
import time
from io import BytesIO
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

import dotenv_loader  # noqa: F401  — must import first: fills os.environ from .env
import feedback as feedback_store
import iosense
import custom_formulas
import expressions
from formulas import UNIT_CONVERSIONS, all_formulas
from report import build_workbook, filename
from validation import SITE_TZ, run_validation

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
DEVICE_CACHE_TTL_S = 300

app = Flask(__name__, static_folder=None)
_device_cache: dict[str, tuple[float, list[dict]]] = {}


def _client() -> iosense.Client:
    token = request.headers.get("Authorization", "").strip()
    # BEARER_TOKEN is a local-development fallback only; in Launchpad the
    # frontend sends the signed-in user's own token.
    token = token or os.environ.get("BEARER_TOKEN", "").strip()
    if not token:
        raise iosense.AuthError("Not signed in. Open Newton from Launchpad.")
    return iosense.Client(token)


def _devices(client: iosense.Client) -> list[dict]:
    key = hashlib.sha256(client.token.encode()).hexdigest()
    now = time.time()
    hit = _device_cache.get(key)
    if hit and now - hit[0] < DEVICE_CACHE_TTL_S:
        return hit[1]
    devices = client.list_devices()
    for k in [k for k, (ts, _) in _device_cache.items() if now - ts >= DEVICE_CACHE_TTL_S]:
        del _device_cache[k]
    _device_cache[key] = (now, devices)
    return devices


@app.errorhandler(iosense.AuthError)
def _auth_error(err):
    return jsonify(error=str(err)), 401


@app.errorhandler(iosense.UpstreamError)
def _upstream_error(err):
    return jsonify(error=f"IOsense platform error: {err}"), 502


@app.errorhandler(ValueError)
def _bad_request(err):
    return jsonify(error=str(err)), 400


@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.post("/api/auth/sso")
def auth_sso():
    sso = (request.get_json(silent=True) or {}).get("token")
    if not sso:
        raise ValueError("Missing 'token'")
    return jsonify(token=iosense.exchange_sso_token(sso))


@app.get("/api/devices")
def devices():
    return jsonify(devices=_devices(_client()))


def _token() -> str:
    return request.headers.get("Authorization", "")


@app.get("/api/formulas")
def formulas():
    return jsonify(formulas=all_formulas(_token()), timezone=SITE_TZ.key,
                   unitConversions=UNIT_CONVERSIONS,
                   expressionHelp={"values": expressions.VALUES, "functions": expressions.FUNCTIONS})


@app.post("/api/formulas/check")
def formulas_check():
    body = request.get_json(silent=True) or {}
    expressions.parse(body.get("expression"))
    return jsonify(ok=True, uses=sorted(expressions.names_used(body.get("expression"))))


@app.post("/api/formulas/custom")
def formulas_create():
    body = request.get_json(silent=True) or {}
    return jsonify(custom_formulas.create(body, _token()))


@app.delete("/api/formulas/custom/<formula_id>")
def formulas_delete(formula_id):
    return jsonify(custom_formulas.delete(formula_id, _token()))


@app.post("/api/validate")
def validate():
    client = _client()
    body = request.get_json(silent=True) or {}
    devices_by_id = {d["devID"]: d for d in _devices(client)}
    return jsonify(run_validation(client, devices_by_id, body, _token()))


@app.post("/api/export")
def export():
    result = request.get_json(silent=True) or {}
    if not isinstance(result.get("rows"), list) or "formula" not in result:
        raise ValueError("Send a validation result to export")
    return send_file(BytesIO(build_workbook(result)), as_attachment=True,
                     download_name=filename(result),
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/feedback")
def feedback():
    body = request.get_json(silent=True) or {}
    entry = feedback_store.record(body, request.headers.get("Authorization", ""))
    return jsonify(ok=True, time=entry["time"])


@app.get("/api/feedback/export.csv")
def feedback_export():
    # Off unless FEEDBACK_ADMIN_KEY is set; a wrong key looks like a missing page.
    if not feedback_store.ADMIN_KEY or request.args.get("key") != feedback_store.ADMIN_KEY:
        return jsonify(error="Not found"), 404
    return Response(feedback_store.export_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=newton-feedback.csv"})


@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def frontend(path: str):
    if path.startswith("api/"):
        return jsonify(error="Not found"), 404
    if path and (DIST / path).is_file():
        return send_from_directory(DIST, path)
    if (DIST / "index.html").is_file():
        return send_from_directory(DIST, "index.html")
    return "Frontend not built. Run: cd frontend && npm install && npm run build", 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7777)))
