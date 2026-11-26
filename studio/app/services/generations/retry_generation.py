from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.models import Generation, GenerationState, Job, JobState, OutputState
from app.services.events import RecordEvent
from app.services.jobs import EnqueueJob
from app.services.outputs import ActionNotAllowed


class RetryGeneration:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation_id: int) -> None:
        generation = self.session.get(Generation, generation_id, with_for_update=True)
        if generation is None or generation.state != GenerationState.FAILED:
            raise ActionNotAllowed("só dá para tentar de novo uma geração que falhou")
        failed = self.session.scalars(select(Job).where(Job.generation_id == generation.id, Job.output_id.is_(None),
                                                        Job.state == JobState.FAILED)
                                      .order_by(Job.id.desc()).limit(1)).first()
        step = failed.step if failed else get_algorithm(generation.algorithm).preparation[0].name
        generation.state = GenerationState.PREPARING
        generation.last_error = None
        for output in generation.outputs:
            if output.state == OutputState.FAILED:
                output.state = OutputState.WAITING
        RecordEvent(self.session).execute(generation.id, "Nova tentativa", f"etapa {step}")
        EnqueueJob(self.session).execute(generation.instance, generation.id, step)
