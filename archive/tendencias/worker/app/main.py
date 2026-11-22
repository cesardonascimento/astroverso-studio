"""API do worker. O n8n (ou você, via curl) chama estes endpoints.
Autenticação: Authorization: Bearer $WORKER_TOKEN (exceto /health)."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from . import jobs
from .config import settings
from .db import run_migrations, tx
from .pipeline import ideas as ideas_pipeline
from .pipeline import trends as trends_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("worker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    loop = jobs.Loop(settings().worker_concurrency)
    loop.start()
    yield
    loop.stop.set()


app = FastAPI(title="astroverso-studio v1 worker", lifespan=lifespan)


def auth(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings().worker_token}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "unauthorized")


@app.get("/health")
def health():
    with tx() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


# ------------------------------------------------------------ tendências
class TrendRefresh(BaseModel):
    country: str | None = None
    period_days: int = 7


@app.post("/trends/refresh", dependencies=[Depends(auth)])
def trends_refresh(body: TrendRefresh):
    return trends_pipeline.refresh(body.country, body.period_days)


@app.get("/trends/themes", dependencies=[Depends(auth)])
def trend_themes(limit: int = 30):
    with tx() as conn:
        return conn.execute(
            "SELECT * FROM trend_themes ORDER BY created_at DESC, fit_score DESC LIMIT %s", (limit,)).fetchall()


# ------------------------------------------------------------ ideias
class IdeaGen(BaseModel):
    count: int = 20
    snapshot_id: int | None = None


@app.post("/ideas/generate", dependencies=[Depends(auth)])
def ideas_generate(body: IdeaGen):
    return ideas_pipeline.generate(body.count, body.snapshot_id)


@app.get("/ideas", dependencies=[Depends(auth)])
def ideas_list(status: str = "proposed", limit: int = 10):
    with tx() as conn:
        return conn.execute(
            "SELECT i.id, i.title, i.hook, i.angle, i.format, i.why_now, i.final_score, i.scores,"
            " i.similarity_max, i.status, t.theme FROM ideas i LEFT JOIN trend_themes t ON t.id = i.theme_id"
            " WHERE i.status=%s ORDER BY i.final_score DESC LIMIT %s", (status, limit)).fetchall()


@app.post("/ideas/{idea_id}/reject", dependencies=[Depends(auth)])
def idea_reject(idea_id: int):
    with tx() as conn:
        conn.execute("UPDATE ideas SET status='rejected', decided_at=now() WHERE id=%s AND status='proposed'",
                     (idea_id,))
    return {"id": idea_id, "status": "rejected"}


# ------------------------------------------------------------ vídeos
class VideoCreate(BaseModel):
    idea_id: int
    settings: dict = {}  # variáveis de experimento: voice, rate, visual_style...


@app.post("/videos", dependencies=[Depends(auth)])
def video_create(body: VideoCreate):
    """Seleciona a ideia e enfileira a produção. Idempotente: se já existe vídeo ativo da ideia, devolve ele."""
    with tx() as conn:
        idea = conn.execute("SELECT status FROM ideas WHERE id=%s FOR UPDATE", (body.idea_id,)).fetchone()
        if not idea:
            raise HTTPException(404, "ideia não existe")
        try:
            with conn.transaction():
                v = conn.execute("INSERT INTO videos (idea_id, settings) VALUES (%s,%s) RETURNING id, state",
                                 (body.idea_id, Jsonb(body.settings))).fetchone()
                conn.execute("INSERT INTO video_events (video_id, to_state, note) VALUES (%s,'QUEUED','criado')",
                             (v["id"],))
        except errors.UniqueViolation:
            v = conn.execute("SELECT id, state FROM videos WHERE idea_id=%s AND state NOT IN"
                             " ('FAILED','CANCELLED','REJECTED')", (body.idea_id,)).fetchone()
            return {**v, "existing": True}
        conn.execute("UPDATE ideas SET status='selected', decided_at=now() WHERE id=%s", (body.idea_id,))
    return {**v, "existing": False}


@app.get("/videos", dependencies=[Depends(auth)])
def videos_list(state: str | None = None, limit: int = 20):
    with tx() as conn:
        return conn.execute(
            "SELECT v.id, v.idea_id, v.state, v.attempts, v.last_error, v.output_path, v.duration_s, v.updated_at,"
            " i.title FROM videos v JOIN ideas i ON i.id=v.idea_id WHERE (%s::text IS NULL OR v.state=%s)"
            " ORDER BY v.updated_at DESC LIMIT %s", (state, state, limit)).fetchall()


@app.get("/videos/{video_id}", dependencies=[Depends(auth)])
def video_get(video_id: int):
    with tx() as conn:
        v = conn.execute("SELECT * FROM videos WHERE id=%s", (video_id,)).fetchone()
        if not v:
            raise HTTPException(404)
        v["script"] = conn.execute("SELECT * FROM scripts WHERE id=%s", (v["script_id"],)).fetchone() \
            if v["script_id"] else None
        v["events"] = conn.execute("SELECT from_state, to_state, note, created_at FROM video_events"
                                   " WHERE video_id=%s ORDER BY id", (video_id,)).fetchall()
        v["cost_usd"] = conn.execute("SELECT coalesce(sum(cost_usd),0) AS c FROM generations WHERE video_id=%s",
                                     (video_id,)).fetchone()["c"]
    return v


@app.get("/videos/{video_id}/file", dependencies=[Depends(auth)])
def video_file(video_id: int):
    with tx() as conn:
        v = conn.execute("SELECT output_path FROM videos WHERE id=%s", (video_id,)).fetchone()
    if not v or not v["output_path"]:
        raise HTTPException(404)
    return FileResponse(settings().media_dir / v["output_path"], media_type="video/mp4")


@app.post("/videos/{video_id}/{action}", dependencies=[Depends(auth)])
def video_action(video_id: int, action: str):
    try:
        if action == "retry":
            return jobs.retry(video_id)
        if action in jobs.MANUAL:
            return jobs.manual(video_id, action)
    except KeyError:
        raise HTTPException(404)
    except ValueError as e:
        raise HTTPException(409, str(e))
    raise HTTPException(400, f"ação desconhecida: {action}")
