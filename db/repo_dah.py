from typing import List, Optional, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session


# --------------------------------------------------------
# Job lifecycle
# --------------------------------------------------------

def create_job(db: Session) -> int:
    """
    Creates a new job with status 'created'.
    Returns deterministic job_seq.
    """

    result = db.execute(
        text("""
            INSERT INTO doc_ai_job (status)
            VALUES ('created')
            RETURNING seq
        """)
    )

    row = result.fetchone()
    return row._mapping["seq"]


def update_job_status(db: Session, job_seq: int, status: str) -> None:
    """
    Updates job status.
    Status must be one of:
    created | processing | completed | failed
    """

    db.execute(
        text("""
            UPDATE doc_ai_job
            SET status = :status
            WHERE seq = :job_seq
        """),
        {
            "status": status,
            "job_seq": job_seq,
        },
    )


# --------------------------------------------------------
# Requests table
# --------------------------------------------------------

def insert_doc_ai_request(
    db: Session,
    job_seq: int,
    space_id: str,
    page_ids: List[str],
    page_titles: List[str],
    user_prompt: str,
    model_output: str,
    model_name: Optional[str],
) -> None:
    """
    Inserts completed model output.
    """

    db.execute(
        text("""
            INSERT INTO doc_ai_requests (
                job_seq,
                space_id,
                page_ids,
                page_title,
                user_prompt,
                model_output,
                model_name
            )
            VALUES (
                :job_seq,
                :space_id,
                :page_ids,
                :page_title,
                :user_prompt,
                :model_output,
                :model_name
            )
        """),
        {
            "job_seq": job_seq,
            "space_id": space_id,
            "page_ids": page_ids,
            "page_title": page_titles,
            "user_prompt": user_prompt,
            "model_output": model_output,
            "model_name": model_name,
        },
    )


# --------------------------------------------------------
# Fetch result
# --------------------------------------------------------

def get_result_by_job_seq(db: Session, job_seq: int) -> Dict:
    """
    Returns:
        {
            status: str,
            model_output: str | None
        }
    """

    job_result = db.execute(
        text("""
            SELECT status
            FROM doc_ai_job
            WHERE seq = :job_seq
        """),
        {"job_seq": job_seq},
    ).fetchone()

    if not job_result:
        raise ValueError("Job not found")

    status = job_result._mapping["status"]

    request_result = db.execute(
        text("""
            SELECT model_output
            FROM doc_ai_requests
            WHERE job_seq = :job_seq
        """),
        {"job_seq": job_seq},
    ).fetchone()

    model_output = None
    if request_result:
        model_output = request_result._mapping["model_output"]

    return {
        "status": status,
        "model_output": model_output,
    }
