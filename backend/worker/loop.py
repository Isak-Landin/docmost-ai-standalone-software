import os
import time
from uuid import UUID

from backend.db import repo
from backend.integrations.docmost_client import fetch_page_content
from backend.integrations.ollama_client import chat
from backend.prompt.prompt_builder import build_messages


def _poll_interval_s() -> float:
    ms = int(os.getenv("WORKER_POLL_INTERVAL_MS", "500"))
    return max(0.05, ms / 1000.0)


def run_forever() -> None:
    # Ensure schema exists (safe if init.sql already handled it)
    repo.ensure_schema()

    poll_s = _poll_interval_s()

    while True:
        job = repo.claim_next_job(from_status="queued", to_status="running")
        if not job:
            time.sleep(poll_s)
            continue

        try:
            if not job.space_id:
                raise RuntimeError("job.space_id is required for docmost fetch")

            space_id = str(job.space_id)

            blobs = []
            for pid in job.selected_page_ids:
                blobs.append(fetch_page_content(space_id=space_id, page_id=str(pid)))

            messages = build_messages(user_message=job.message, page_blobs=blobs)
            final_text = chat(messages=messages)

            repo.set_job_done(job_id=job.id, status="done", final_text=final_text)

        except Exception as e:
            logger.warning(f"An Error occurred during runtime " + f"str(e)")
            repo.set_job_failed(job_id=job.id, status="failed", error_text=str(e))
