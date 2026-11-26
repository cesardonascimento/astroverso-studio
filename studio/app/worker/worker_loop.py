import logging
import threading
from pathlib import Path

from app.lib.database import open_session
from app.worker.claim_job import ClaimJob
from app.worker.run_job import RunJob

log = logging.getLogger(__name__)


class WorkerLoop:
    def __init__(self, database_url: str, instance: str, workspace: Path, stop: threading.Event):
        self.database_url = database_url
        self.instance = instance
        self.workspace = workspace
        self.stop = stop

    def execute(self) -> None:
        while not self.stop.is_set():
            try:
                with open_session(self.database_url) as session:
                    job = ClaimJob(session).execute(self.instance)
                    job_id = job.id if job else None
                if job_id is None:
                    self.stop.wait(2)
                    continue
                RunJob(self.database_url, self.workspace).execute(job_id)
            except Exception:
                log.exception("erro no worker")
                self.stop.wait(10)
