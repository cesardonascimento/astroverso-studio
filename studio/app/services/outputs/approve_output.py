from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.algorithms.base import StepFailed
from app.config import WORK_DIR
from app.models import OutputState, OutputVersion, VersionKind
from app.services.events import RecordEvent
from app.services.jobs import EnqueueJob
from app.services.outputs.action_not_allowed import ActionNotAllowed
from app.services.outputs.load_output import LoadOutput


class ApproveOutput:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int, edits: dict[str, list[str]] | None = None) -> None:
        output = LoadOutput(self.session).execute(output_id)
        if output.state != OutputState.AWAITING_APPROVAL:
            raise ActionNotAllowed("este roteiro não está aguardando aprovação")
        generation = output.generation
        algorithm = get_algorithm(generation.algorithm)
        current = output.versions[-1]
        if edits and algorithm.plan_editor:
            try:
                edited = algorithm.plan_editor().execute(generation, current.plan, edits, WORK_DIR)
            except StepFailed as error:
                raise ActionNotAllowed(str(error)) from error
            if edited != current.plan:
                output.current_version += 1
                output.versions.append(OutputVersion(version=output.current_version, kind=VersionKind.EDIT,
                                                     request="edição manual", plan=edited,
                                                     strategy_name=current.strategy_name,
                                                     strategy_text=current.strategy_text))
        output.state = OutputState.RENDERING
        output.approved_at = datetime.now(timezone.utc)
        output.last_error = None
        RecordEvent(self.session).execute(generation.id, "Aprovação", f"roteiro v{output.current_version} aprovado",
                                          output.id)
        EnqueueJob(self.session).execute(generation.instance, generation.id, algorithm.rendering[0].name, output.id)
