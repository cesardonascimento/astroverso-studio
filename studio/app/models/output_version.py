from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class VersionKind:
    INITIAL = "initial"
    REPLAN = "replan"
    REVISION = "revision"
    EDIT = "edit"


class OutputVersion(Base):
    __tablename__ = "output_versions"
    __table_args__ = (UniqueConstraint("output_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    output_id: Mapped[int] = mapped_column(ForeignKey("outputs.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    kind: Mapped[str] = mapped_column(String(16))
    request: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[dict] = mapped_column(JSONB)
    strategy_name: Mapped[str] = mapped_column(String(64))
    strategy_text: Mapped[str] = mapped_column(Text, default="")
    video_key: Mapped[str | None] = mapped_column(Text)
    duration_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    render_report: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    output: Mapped["Output"] = relationship(back_populates="versions")
