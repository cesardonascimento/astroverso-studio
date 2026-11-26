from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.models import OutputState, VersionKind
from app.services.events import RecordEvent
from app.services.jobs import CancelPendingJobs, EnqueueJob
from app.services.outputs.action_not_allowed import ActionNotAllowed
from app.services.outputs.load_output import LoadOutput

ALLOWED = {OutputState.AWAITING_APPROVAL, OutputState.DONE, OutputState.FAILED}


class ReplanOutput:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int, request: str, kind: str = VersionKind.REPLAN) -> None:
        output = LoadOutput(self.session).execute(output_id)
        if output.state not in ALLOWED or not output.versions:
            raise ActionNotAllowed("ainda não há roteiro para refazer")
        if kind == VersionKind.REVISION and output.state != OutputState.DONE:
            raise ActionNotAllowed("alterações só depois do vídeo pronto")
        if kind == VersionKind.REVISION and not request.strip():
            raise ActionNotAllowed("descreva a alteração")
        generation = output.generation
        CancelPendingJobs(self.session).execute(generation.id, output.id)
        output.pending_request = {"kind": kind, "text": request.strip()}
        output.state = OutputState.PLANNING
        output.last_error = None
        label = "Alteração pedida" if kind == VersionKind.REVISION else "Novo roteiro pedido"
        RecordEvent(self.session).execute(generation.id, label, request.strip() or "sem instruções", output.id)
        EnqueueJob(self.session).execute(generation.instance, generation.id,
                                         get_algorithm(generation.algorithm).planning.name, output.id)
