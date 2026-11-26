import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import APP_DIR, WORK_DIR, settings
from app.controllers import auth, generations, new_generation, outputs
from app.controllers.require_login import RequireLogin
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
app.add_middleware(RequireLogin)
app.add_middleware(SessionMiddleware, secret_key=settings().secret_key, session_cookie="studio_session",
                   max_age=60 * 60 * 24 * 30, same_site="lax")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.include_router(auth.router)
app.include_router(new_generation.router)
app.include_router(generations.router)
app.include_router(outputs.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
