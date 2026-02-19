import json
import os
import time
from typing import Any, Dict, List
from uuid import UUID

from flask import Flask, Response, jsonify, request

from backend.db import repo


def _statuses_from_env() -> List[str]:
    raw = os.getenv("JOB_STATUSES", "queued,running,done,failed")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def register_routes(app: Flask) -> None:
    job_create_path = os.getenv("JOB_CREATE_PATH", "/api/jobs")
    sse_path = os.getenv("SSE_PATH", "/api/sse")
    poll_ms = int(os.getenv("WORKER_POLL_INTERVAL_MS", "500"))

    statuses = _statuses_from_env()
    queued = "queued"
    done = "done"
    failed = "failed"

    @app.post(job_create_path)
    def create_job():
        payload = request.get_json(silent=True) or {}

        # Minimal stable contract
        space_id = (payload.get("space_id") or "").strip() or None
        selected = payload.get("selected_page_ids") or []
        user_prompt = (payload.get("message") or "").strip()

        if not user_prompt:
            return jsonify({
                "ok": False,
                "error": "missing_user_prompt",
                "message": "Make sure to pass the user prompt if you are attempting to write a message"
            }), 400

        # Accept UUID strings; store as UUIDs
        try:
            space_uuid = UUID(space_id) if space_id else None
            selected_uuids = [UUID(str(x)) for x in selected]
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"{e}",
                "message": "Something went wrong http/routes when attempting to create and store job"
            }), 400

        if queued not in statuses:
            return jsonify({
                "ok": False,
                "error": "invalid_status_config",
                "message": "Runtime expected enums and actual enums mismatch when trying to create and store job"
            }), 500

        job_id = repo.create_job(
            status=queued,
            space_id=space_uuid,
            selected_page_ids=selected_uuids,
            message=user_prompt,
        )

        return jsonify({"ok": True, "job_id": str(job_id)})

    @app.get(sse_path)
    def sse():
        job_id_raw = (request.args.get("job_id") or "").strip()
        if not job_id_raw:
            return jsonify({
                "ok": False,
                "error": "missing_job_id",
                "message": "When attempting to fetch/sse for job, ensure you pass the job_id and as correct key"
            }), 400
        try:
            job_id = UUID(job_id_raw)
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"{str(e)}",
                "Message": "Make sure you are passing the correct id, uuid. When converting it we ran into an issue"
            }), 400

        def gen():
            last_status = None
            sent_final = False

            while True:
                j = repo.get_job(job_id=job_id)
                if not j:
                    yield _sse("error", {
                        "job_id": job_id_raw,
                        "error": "job_id row not_found in db",
                        "message": "Double check the job_id value to receive sse event"
                    })
                    return

                if j.status != last_status:
                    last_status = j.status
                    yield _sse("job_status", {
                        "job_id": job_id_raw,
                        "status": j.status
                    })

                if not sent_final and j.status == done and (j.final_text is not None):
                    sent_final = True
                    yield _sse("final", {
                        "job_id": job_id_raw,
                        "final_text": j.final_text
                    })
                    return

                if j.status == failed and (j.error_text is not None):
                    yield _sse("error", {
                        "job_id": job_id_raw,
                        "error_text": j.error_text,
                        "message": "We ran into an issue when attempting to modify or manage a job row"
                    })
                    return

                time.sleep(max(0.05, poll_ms / 1000.0))

        return Response(gen(), mimetype="text/event-stream")


