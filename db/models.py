# db/models.py
from __future__ import annotations

import enum
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DocAIJobStatus(str, enum.Enum):
    created = "created"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class DocAIJob(Base):
    __tablename__ = "doc_ai_job"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # seq is GENERATED ALWAYS AS IDENTITY in SQL; treat as server-generated.
    seq: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    status: Mapped[DocAIJobStatus] = mapped_column(
        SAEnum(DocAIJobStatus, name="doc_ai_job_status"),
        nullable=False,
        server_default=DocAIJobStatus.created.value,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    requests: Mapped[list["DocAIRequest"]] = relationship(
        back_populates="job",
        primaryjoin="DocAIJob.seq==foreign(DocAIRequest.job_seq)",
        cascade="",
    )

    __table_args__ = (
        Index("idx_doc_ai_job_status_seq", "status", "seq"),
    )


class DocAIRequest(Base):
    __tablename__ = "doc_ai_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    job_seq: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("doc_ai_job.seq", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    space_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    page_ids: Mapped[list[UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    page_title: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False)

    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model_output: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["DocAIJob"] = relationship(
        back_populates="requests",
        primaryjoin="foreign(DocAIRequest.job_seq)==DocAIJob.seq",
    )

    __table_args__ = (
        Index("idx_doc_ai_requests_job_seq", "job_seq"),
        Index("idx_doc_ai_requests_space_created", "space_id", "created_at"),
    )
