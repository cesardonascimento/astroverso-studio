from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import WORK_DIR
from app.dependencies import delete_object
from app.models import Generation, GenerationState, OutputState
from app.services.events import RecordEvent
from app.services.outputs import ActionNotAllowed

BUSY = {OutputState.WAITING, OutputState.PLANNING, OutputState.RENDERING}


class DeleteOriginal:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation_id: int) -> None:
        generation = self.session.get(Generation, generation_id, with_for_update=True)
        if generation is None:
            raise LookupError(f"geração {generation_id} não encontrada")
        if not generation.original_key:
            raise ActionNotAllowed("o original já foi apagado")
        if generation.state == GenerationState.PREPARING or any(output.state in BUSY for output in generation.outputs):
            raise ActionNotAllowed("espere as etapas em andamento terminarem")
        delete_object().execute(generation.original_key)
        (WORK_DIR / "generations" / str(generation.id) / "original.mp4").unlink(missing_ok=True)
        generation.original_key = None
        generation.original_deleted_at = datetime.now(timezone.utc)
        RecordEvent(self.session).execute(generation.id, "Original apagado",
                                          "novos roteiros e renders deixam de ser possíveis")
