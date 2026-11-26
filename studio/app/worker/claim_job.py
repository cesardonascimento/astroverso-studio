from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Job, JobState

LEASE = timedelta(minutes=60)


class ClaimJob:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, instance: str) -> Job | None:
        now = func.now()
        job = self.session.scalars(
            select(Job)
            .where(Job.instance == instance,
                   or_(and_(Job.state == JobState.QUEUED, Job.run_after <= now),
                       and_(Job.state == JobState.RUNNING, Job.locked_until < now)))
            .order_by(Job.id).limit(1).with_for_update(skip_locked=True)).first()
        if job is None:
            return None
        job.state = JobState.RUNNING
        job.attempts += 1
        job.locked_until = now + LEASE
        return job
