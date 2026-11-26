from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[int] = mapped_column(ForeignKey("generations.id", ondelete="CASCADE"), index=True)
    output_id: Mapped[int | None] = mapped_column(ForeignKey("outputs.id", ondelete="CASCADE"))
    step: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    ok: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    generation: Mapped["Generation"] = relationship(back_populates="events")
