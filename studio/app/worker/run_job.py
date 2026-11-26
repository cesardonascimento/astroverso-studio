import logging
import time
from datetime import timedelta

from sqlalchemy import func

from app.ai.claude import ClaudeCallFailed
from app.algorithms import get_algorithm
from app.algorithms.base import StepContext, StepFailed
from app.lib.database import open_session
from app.models import Generation, GenerationState, Job, JobState, Output, OutputState
from app.services.costs import RecordLlmCall
from app.services.events import RecordEvent
from app.worker.advance_flow import AdvanceFlow

log = logging.getLogger(__name__)
CANCELLED = {GenerationState.CANCELLED, OutputState.CANCELLED}


class RunJob:
    def __init__(self, database_url: str, workspace):
        self.database_url = database_url
        self.workspace = workspace

    def execute(self, job_id: int) -> None:
        started = time.monotonic()
        try:
            with open_session(self.database_url) as session:
                job = session.get(Job, job_id)
                generation = session.get(Generation, job.generation_id)
                output = session.get(Output, job.output_id) if job.output_id else None
                if generation.state in CANCELLED or (output and output.state in CANCELLED):
                    job.state = JobState.CANCELLED
                    return
                algorithm = get_algorithm(generation.algorithm)
                step = algorithm.step_named(job.step)()
                message = step.execute(StepContext(session, generation, self.workspace, output))
                RecordEvent(session).execute(generation.id, step.label or step.name,
                                             f"{message} · {time.monotonic() - started:.0f} s", job.output_id)
                job.state = JobState.DONE
                job.locked_until = None
                job.last_error = None
                AdvanceFlow(session).execute(algorithm, job, generation, output)
        except Exception as error:
            log.exception("job %s falhou", job_id)
            self._register_failure(job_id, error)

    def _register_failure(self, job_id: int, error: Exception) -> None:
        with open_session(self.database_url) as session:
            job = session.get(Job, job_id)
            generation = session.get(Generation, job.generation_id)
            output = session.get(Output, job.output_id) if job.output_id else None
            if isinstance(error, ClaudeCallFailed):
                RecordLlmCall(session).execute(generation, job.step, error.usage)
            text = str(error) or repr(error)
            job.last_error = text[:4000]
            job.locked_until = None
            if isinstance(error, StepFailed) or job.attempts >= job.max_attempts:
                job.state = JobState.FAILED
                self._mark_failed(generation, output, text)
                RecordEvent(session).execute(generation.id, job.step, f"falhou: {text}", job.output_id, ok=False)
                return
            wait = 4 ** (job.attempts - 1)
            job.state = JobState.QUEUED
            job.run_after = func.now() + timedelta(minutes=wait)
            RecordEvent(session).execute(generation.id, job.step,
                                         f"tentativa {job.attempts} falhou ({text[:300]}); "
                                         f"nova tentativa em {wait} min", job.output_id, ok=False)

    def _mark_failed(self, generation: Generation, output: Output | None, text: str) -> None:
        if output is None:
            generation.state = GenerationState.FAILED
            generation.last_error = text[:4000]
            for item in generation.outputs:
                if item.state == OutputState.WAITING:
                    item.state = OutputState.FAILED
            return
        output.state = OutputState.FAILED
        output.last_error = text[:4000]
