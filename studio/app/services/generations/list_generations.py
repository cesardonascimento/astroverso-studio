from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Generation, Output


class ListGenerations:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, limit: int = 50) -> list[Generation]:
        return list(self.session.scalars(
            select(Generation).options(selectinload(Generation.outputs).selectinload(Output.versions))
            .order_by(Generation.id.desc()).limit(limit)))
