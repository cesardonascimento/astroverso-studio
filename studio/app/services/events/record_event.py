from sqlalchemy.orm import Session

from app.models import Event


class RecordEvent:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation_id: int, step: str, message: str, output_id: int | None = None,
                ok: bool = True) -> Event:
        event = Event(generation_id=generation_id, output_id=output_id, step=step, message=message[:2000], ok=ok)
        self.session.add(event)
        return event
