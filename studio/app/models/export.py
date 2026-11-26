from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps


class ExportState:
    PENDING = "PENDING"
    DONE = "DONE"
    FAILED = "FAILED"


class Export(Timestamps, Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    output_version_id: Mapped[int] = mapped_column(ForeignKey("output_versions.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), default=ExportState.PENDING)
    remote_path: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
