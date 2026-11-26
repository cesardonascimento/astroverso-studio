import logging
import time
from datetime import timedelta

from sqlalchemy import func

from app.ai.claude import ClaudeCallFailed
from app.algorithms import get_algorithm
from app.algorithms.base import StepContext, StepFailed
from app.lib.database import open_session
from app.models import Export, ExportState, Generation, GenerationState, Job, JobState, Output, OutputState, OutputVersion
from app.services.costs import RecordLlmCall
from app.services.events import RecordEvent
from app.worker.advance_flow import AdvanceFlow
from app.worker.export_step import ExportStep

SYSTEM_STEPS = {ExportStep.name: ExportStep}

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
                step = (SYSTEM_STEPS.get(job.step) or algorithm.step_named(job.step))()
                message = step.execute(StepContext(session, generation, self.workspace, output))
                RecordEvent(session).execute(generation.id, step.label or step.name,
                                             f"{message} · {time.monotonic() - started:.0f} s", job.output_id)
                job.state = JobState.DONE
                job.locked_until = None
                job.last_error = None
                if job.step not in SYSTEM_STEPS:
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
            label = self._label(generation, job.step)
            job.last_error = text[:4000]
            job.locked_until = None
            permanent = isinstance(error, StepFailed) or getattr(error, "permanent", False)
            if permanent or job.attempts >= job.max_attempts:
                job.state = JobState.FAILED
                if job.step in SYSTEM_STEPS:
                    self._mark_export_failed(session, output, text)
                else:
                    self._mark_failed(generation, output, text)
                RecordEvent(session).execute(generation.id, label, f"falhou: {text}", job.output_id, ok=False)
                return
            wait = 4 ** (job.attempts - 1)
            job.state = JobState.QUEUED
            job.run_after = func.now() + timedelta(minutes=wait)
            RecordEvent(session).execute(generation.id, label,
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

    def _mark_export_failed(self, session, output: Output, text: str) -> None:
        for export in session.query(Export).join(OutputVersion).filter(OutputVersion.output_id == output.id,
                                                                       Export.state == ExportState.PENDING):
            export.state = ExportState.FAILED
            export.last_error = text[:4000]

    def _label(self, generation: Generation, step_name: str) -> str:
        step = SYSTEM_STEPS.get(step_name)
        if step is None:
            try:
                step = get_algorithm(generation.algorithm).step_named(step_name)
            except LookupError:
                return step_name
        return step.label or step_name
