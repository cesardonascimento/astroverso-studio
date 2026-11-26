import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import APP_DIR, WORK_DIR, settings
from app.dependencies import storage_client
from app.lib.database.migrate import MigrateDatabase
from app.lib.s3 import EnsureBucket
from app.worker import WorkerLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    config = settings()
    MigrateDatabase(APP_DIR.parent / "alembic.ini").execute(config.database_url)
    EnsureBucket(storage_client()).execute(config.s3_bucket)
    stop = threading.Event()
    worker = WorkerLoop(config.database_url, config.instance_name, WORK_DIR, stop)
    threading.Thread(target=worker.execute, daemon=True, name="worker").start()
    yield
    stop.set()


app = FastAPI(title="Astroverso Studio", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
