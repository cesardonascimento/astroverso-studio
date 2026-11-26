from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import APP_DIR, settings
from app.lib.database.migrate import MigrateDatabase


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    MigrateDatabase(APP_DIR.parent / "alembic.ini").execute(settings().database_url)
    yield


app = FastAPI(title="Astroverso Studio", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
