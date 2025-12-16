import threading
from flask import jsonify
from pipeline import run_pipeline

def main(request):
    if request.method != "POST":
        return "Only POST allowed", 405

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Invalid JSON"}), 400

    threading.Thread(
        target=run_pipeline,
        args=(payload, None)
    ).start()

    return "Summary PDF pipeline started", 202
