from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Job, JobState


class CancelPendingJobs:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, generation_id: int, output_id: int | None = None) -> None:
        query = update(Job).where(Job.generation_id == generation_id, Job.state == JobState.QUEUED)
        if output_id is not None:
            query = query.where(Job.output_id == output_id)
        self.session.execute(query.values(state=JobState.CANCELLED))
