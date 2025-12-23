import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request

from pipeline import run_pipeline
from test_pipeline import run_test_pipeline

try:
    from odoo_client import ping_odoo
except Exception:
    ping_odoo = None

app = Flask(__name__)


UPLOAD_KEY_CANDIDATES = ["signed_pdf", "file", "pdf"]


def _parse_payload() -> dict:
    # Primary: JSON body
    if request.is_json:
        payload = request.get_json(silent=True)
        if payload is None:
            raise ValueError("Invalid JSON payload")
        return payload

    # Multipart or form: expect a 'payload' field containing JSON text
    payload_text = request.form.get("payload")
    if payload_text:
        try:
            return json.loads(payload_text)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid payload JSON text: {exc}")

    raise ValueError("No payload provided")


def _save_uploaded_pdf() -> Optional[str]:
    if not request.files:
        return None

    for key in UPLOAD_KEY_CANDIDATES:
        file = request.files.get(key)
        if file and file.filename:
            fd, tmp_path = tempfile.mkstemp(suffix=Path(file.filename).suffix or ".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(file.read())
            return tmp_path
    return None


def _start_async_pipeline(payload: dict, signed_pdf_path: str | None = None, delete_after: bool = False):
    def _run():
        try:
            run_pipeline(payload, signed_pdf_path)
        finally:
            if delete_after and signed_pdf_path:
                try:
                    Path(signed_pdf_path).unlink(missing_ok=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"Warning: failed to delete uploaded PDF {signed_pdf_path}: {exc}")

    threading.Thread(target=_run).start()


@app.post("/")
def start_pipeline_route():
    try:
        payload = _parse_payload()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    uploaded_pdf = _save_uploaded_pdf()
    delete_after = uploaded_pdf is not None

    _start_async_pipeline(payload, uploaded_pdf, delete_after=delete_after)
    return jsonify({"message": "Summary PDF pipeline started"}), 202


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.get("/test")
def run_test_route():
    try:
        outputs = run_test_pipeline()
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "message": "Test pipeline completed. Check the output folder inside the container volume.",
        "outputs": outputs,
    }), 200


@app.get("/ping-odoo")
def ping_odoo_route():
    if ping_odoo is None:
        return jsonify({"error": "Odoo client not available"}), 500

    try:
        res = ping_odoo()
        return jsonify({"status": "ok", "result": res}), 200
    except ValueError as cfg_err:
        return jsonify({"error": f"Missing config: {cfg_err}"}), 400
    except Exception as exc:  # noqa: BLE001 broad to surface any auth/network issue
        return jsonify({"error": str(exc)}), 502


def main(request):
    if request.method != "POST":
        return "Only POST allowed", 405

    try:
        payload = request.get_json(silent=True)
        if not payload:
            raise ValueError("Invalid JSON")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    _start_async_pipeline(payload, None)
    return "Summary PDF pipeline started", 202


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
