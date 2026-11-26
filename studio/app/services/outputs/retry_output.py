from sqlalchemy import select
from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.models import Job, JobState, OutputState
from app.services.events import RecordEvent
from app.services.jobs import EnqueueJob
from app.services.outputs.action_not_allowed import ActionNotAllowed
from app.services.outputs.load_output import LoadOutput


class RetryOutput:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int) -> None:
        output = LoadOutput(self.session).execute(output_id)
        if output.state != OutputState.FAILED:
            raise ActionNotAllowed("só dá para tentar de novo uma saída que falhou")
        failed = self.session.scalars(select(Job).where(Job.output_id == output.id, Job.state == JobState.FAILED)
                                      .order_by(Job.id.desc()).limit(1)).first()
        generation = output.generation
        algorithm = get_algorithm(generation.algorithm)
        step = failed.step if failed else algorithm.planning.name
        output.state = OutputState.PLANNING if step == algorithm.planning.name else OutputState.RENDERING
        output.last_error = None
        RecordEvent(self.session).execute(generation.id, "Nova tentativa", f"etapa {step}", output.id)
        EnqueueJob(self.session).execute(generation.instance, generation.id, step, output.id)
