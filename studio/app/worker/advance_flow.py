from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.algorithms.base import Algorithm
from app.models import Generation, GenerationState, Job, Output, OutputState, VersionKind
from app.services.exports import RequestExport
from app.services.jobs import EnqueueJob


class AdvanceFlow:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, algorithm: Algorithm, job: Job, generation: Generation, output: Output | None) -> None:
        following = algorithm.step_after(job.step)
        if following is not None:
            EnqueueJob(self.session).execute(generation.instance, generation.id, following.name, job.output_id)
        elif output is None:
            self._start_planning(algorithm, generation)
        elif job.step == algorithm.planning.name:
            self._after_planning(algorithm, generation, output)
        else:
            output.state = OutputState.DONE
            RequestExport(self.session).execute(output)

    def _start_planning(self, algorithm: Algorithm, generation: Generation) -> None:
        generation.state = GenerationState.READY
        for output in generation.outputs:
            if output.state == OutputState.WAITING:
                output.state = OutputState.PLANNING
                EnqueueJob(self.session).execute(generation.instance, generation.id, algorithm.planning.name,
                                                 output.id)

    def _after_planning(self, algorithm: Algorithm, generation: Generation, output: Output) -> None:
        revision = output.versions[-1].kind == VersionKind.REVISION
        if revision or output.options.get("auto_approve"):
            output.state = OutputState.RENDERING
            output.approved_at = datetime.now(timezone.utc)
            EnqueueJob(self.session).execute(generation.instance, generation.id, algorithm.rendering[0].name,
                                             output.id)
        else:
            output.state = OutputState.AWAITING_APPROVAL
