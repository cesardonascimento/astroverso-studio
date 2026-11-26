from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.models import Generation, GenerationState, Output, OutputState

FILTERS = {
    "active": [GenerationState.PREPARING, OutputState.WAITING, OutputState.PLANNING, OutputState.RENDERING],
    "approval": [OutputState.AWAITING_APPROVAL],
    "done": [OutputState.DONE],
    "failed": [GenerationState.FAILED, OutputState.FAILED],
}


class ListGenerations:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, state_filter: str = "", instance: str = "", limit: int = 100) -> list[Generation]:
        query = (select(Generation).options(selectinload(Generation.outputs).selectinload(Output.versions))
                 .order_by(Generation.id.desc()).limit(limit))
        if instance:
            query = query.where(Generation.instance == instance)
        states = FILTERS.get(state_filter)
        if states:
            has_output = exists().where(Output.generation_id == Generation.id, Output.state.in_(states))
            query = query.where(Generation.state.in_(states) | has_output)
        return list(self.session.scalars(query))
