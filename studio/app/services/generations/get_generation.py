from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Generation, Output


class GetGeneration:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation_id: int) -> Generation:
        generation = self.session.scalars(
            select(Generation).where(Generation.id == generation_id)
            .options(selectinload(Generation.outputs).selectinload(Output.versions),
                     selectinload(Generation.events))).first()
        if generation is None:
            raise LookupError(f"geração {generation_id} não encontrada")
        return generation
