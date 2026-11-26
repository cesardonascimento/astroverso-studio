from sqlalchemy.orm import Session

from app.models import OutputState
from app.services.events import RecordEvent
from app.services.jobs import CancelPendingJobs
from app.services.outputs.load_output import LoadOutput


class CancelOutput:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int) -> None:
        output = LoadOutput(self.session).execute(output_id)
        CancelPendingJobs(self.session).execute(output.generation_id, output.id)
        output.state = OutputState.CANCELLED
        RecordEvent(self.session).execute(output.generation_id, "Cancelado", f"saída {output.network} cancelada",
                                          output.id)
