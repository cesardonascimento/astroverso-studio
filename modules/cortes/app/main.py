"""API do worker de cortes. Authorization: Bearer $WORKER_TOKEN (exceto /health)."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from . import jobs
from .config import settings
from .db import run_migrations, tx
from .pipeline import plan as planner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    loop = jobs.Loop(settings().worker_concurrency)
    loop.start()
    yield
    loop.stop.set()


app = FastAPI(title="astroverso-studio · módulo cortes", lifespan=lifespan)


def auth(authorization: str = Header(default="")) -> None:
    if not hmac.compare_digest(authorization.encode(), f"Bearer {settings().worker_token}".encode()):
        raise HTTPException(401, "unauthorized")


@app.get("/health")
def health():
    with tx() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


class JobCreate(BaseModel):
    url: str
    auto_approve: bool = False      # pula a aprovação do roteiro
    max_duration_s: int | None = None
    layout: str | None = None       # auto | crop | fit_blur | split
    crop_x: float | None = None     # só para crop: 0 esquerda, 0.5 centro, 1 direita
    top_box: list[float] | None = None     # só para split: [x, y, w, h] normalizados
    bottom_box: list[float] | None = None  # só para split (ex.: a webcam de um react)
    subtitle_preset: str | None = None     # nome em config/presets.json
    instructions: str | None = None # prompt adicional: como você quer o corte/edição
    rights_note: str | None = None  # de onde vem a autorização para cortar
    context: dict = {}              # origem do pedido


@app.post("/jobs", dependencies=[Depends(auth)])
def job_create(body: JobCreate):
    opts = body.model_dump(exclude={"url", "rights_note", "instructions", "context"}, exclude_none=True)
    with tx() as conn:
        j = conn.execute(
            "INSERT INTO jobs (url, options, rights_note, instructions, context) VALUES (%s,%s,%s,%s,%s)"
            " RETURNING id, state",
            (body.url, Jsonb(opts), body.rights_note, (body.instructions or "").strip() or None,
             Jsonb(body.context))).fetchone()
        conn.execute("INSERT INTO job_events (job_id, to_state, note) VALUES (%s,'QUEUED','criado')", (j["id"],))
    return j


@app.get("/presets", dependencies=[Depends(auth)])
def get_presets():
    from .config import presets
    from .render.effects import available
    return {**presets(), "effects": available()}


@app.get("/jobs/{job_id}/plans", dependencies=[Depends(auth)])
def job_plans(job_id: int):
    with tx() as conn:
        return conn.execute("SELECT version, kind, request, plan->>'changes' AS changes, output_path, created_at"
                            " FROM job_plans WHERE job_id=%s ORDER BY version", (job_id,)).fetchall()


@app.get("/jobs", dependencies=[Depends(auth)])
def job_list(limit: int = 20):
    with tx() as conn:
        return conn.execute(
            "SELECT id, state, source_title, source_channel, plan->>'title' AS cut_title, output_duration_s,"
            " last_error, updated_at FROM jobs ORDER BY id DESC LIMIT %s", (limit,)).fetchall()


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def job_get(job_id: int):
    with tx() as conn:
        j = conn.execute(
            "SELECT id, url, state, source_title, source_channel, source_duration_s, transcript_source,"
            " jsonb_array_length(coalesce(transcript,'[]')) AS transcript_words, plan, plan_version, options,"
            " rights_note, instructions, context, pending_request,"
            " output_path, output_duration_s, qc_report, attempts, last_error, created_at, updated_at"
            " FROM jobs WHERE id=%s", (job_id,)).fetchone()
        if not j:
            raise HTTPException(404)
        j["events"] = conn.execute("SELECT from_state, to_state, note, created_at FROM job_events"
                                   " WHERE job_id=%s ORDER BY id", (job_id,)).fetchall()
    return j


@app.get("/jobs/{job_id}/preview", dependencies=[Depends(auth)], response_class=PlainTextResponse)
def job_preview(job_id: int):
    j = jobs.load(job_id)
    if not j:
        raise HTTPException(404)
    return planner.preview(j)


@app.get("/jobs/{job_id}/file", dependencies=[Depends(auth)])
def job_file(job_id: int, preview: bool = False):
    j = jobs.load(job_id)
    if not j or not j["output_path"]:
        raise HTTPException(404)
    rel = ((j["qc_report"] or {}).get("render") or {}).get("preview_path") if preview else j["output_path"]
    if not rel:
        raise HTTPException(404)
    return FileResponse(settings().media_dir / rel, media_type="video/mp4")


@app.post("/jobs/{job_id}/{action}", dependencies=[Depends(auth)])
def job_action(job_id: int, action: str, body: dict = Body(default={})):
    try:
        return jobs.act(job_id, action, body or {})
    except KeyError:
        raise HTTPException(404)
    except LookupError:
        raise HTTPException(400, f"ação desconhecida: {action}")
    except ValueError as e:
        raise HTTPException(409, str(e))
