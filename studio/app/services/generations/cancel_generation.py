from sqlalchemy.orm import Session

from app.models import Generation, GenerationState, OutputState
from app.services.events import RecordEvent
from app.services.jobs import CancelPendingJobs

FINAL = {OutputState.DONE, OutputState.CANCELLED}


class CancelGeneration:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation_id: int) -> None:
        generation = self.session.get(Generation, generation_id, with_for_update=True)
        if generation is None:
            raise LookupError(f"geração {generation_id} não encontrada")
        CancelPendingJobs(self.session).execute(generation.id)
        if generation.state == GenerationState.PREPARING:
            generation.state = GenerationState.CANCELLED
        for output in generation.outputs:
            if output.state not in FINAL:
                output.state = OutputState.CANCELLED
        RecordEvent(self.session).execute(generation.id, "Cancelado", "geração cancelada")
