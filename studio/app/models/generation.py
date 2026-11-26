from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps


class GenerationState:
    PREPARING = "PREPARING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Generation(Timestamps, Base):
    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(primary_key=True)
    instance: Mapped[str] = mapped_column(String(64), index=True)
    algorithm: Mapped[str] = mapped_column(String(64))
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(String(32), default=GenerationState.PREPARING)
    title: Mapped[str | None] = mapped_column(Text)
    source: Mapped[dict] = mapped_column(JSONB, default=dict)
    original_key: Mapped[str | None] = mapped_column(Text)
    original_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 5), default=0)

    outputs: Mapped[list["Output"]] = relationship(back_populates="generation", order_by="Output.id")
    events: Mapped[list["Event"]] = relationship(back_populates="generation", order_by="Event.id")
