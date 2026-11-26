from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps


class JobState:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Job(Timestamps, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("jobs_claim_idx", "instance", "state", "run_after"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instance: Mapped[str] = mapped_column(String(64))
    generation_id: Mapped[int] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), index=True)
    output_id: Mapped[int | None] = mapped_column(ForeignKey("outputs.id", ondelete="CASCADE"))
    step: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default=JobState.QUEUED)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
