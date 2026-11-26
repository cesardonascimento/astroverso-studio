from sqlalchemy.orm import Session

from app.models import Job, JobState


class EnqueueJob:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, instance: str, generation_id: int, step: str, output_id: int | None = None) -> Job:
        job = Job(instance=instance, generation_id=generation_id, output_id=output_id, step=step)
        self.session.add(job)
        return job

