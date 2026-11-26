from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps


class OutputState:
    WAITING = "WAITING"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    RENDERING = "RENDERING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Output(Timestamps, Base):
    __tablename__ = "outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[int] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), index=True)
    network: Mapped[str] = mapped_column(String(64))
    strategy: Mapped[str] = mapped_column(String(64))
    options: Mapped[dict] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(String(32), default=OutputState.WAITING)
    current_version: Mapped[int] = mapped_column(default=0)
    pending_request: Mapped[dict | None] = mapped_column(JSONB)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    generation: Mapped["Generation"] = relationship(back_populates="outputs")
    versions: Mapped[list["OutputVersion"]] = relationship(back_populates="output", order_by="OutputVersion.version")
