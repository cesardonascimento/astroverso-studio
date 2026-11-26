"""Fila de jobs no Postgres + etapas do corte.

QUEUED → [download] → DOWNLOADED → [transcrição] → TRANSCRIBED → [plano] → AWAITING_APPROVAL
   (você aprova; ou auto_approve) → APPROVED → [render] → RENDERED → [QC] → DONE | QC_FAILED
"""
from __future__ import annotations

import logging
import threading
import time

from psycopg.types.json import Jsonb

from .config import settings, subtitle_style
from .db import tx
from .pipeline import plan as planner
from .pipeline import source
from .render import cut

log = logging.getLogger(__name__)
LEASE = "60 minutes"  # download + whisper de vídeo longo pode demorar


class StepFailed(RuntimeError):
    """Falha que não adianta repetir."""


def load(job_id: int) -> dict | None:
    with tx() as conn:
        return conn.execute("SELECT * FROM jobs WHERE id=%s", (job_id,)).fetchone()


def update(job_id: int, **fields) -> None:
    sets = ", ".join(f"{k}=%s" for k in fields)
    vals = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in fields.values()]
    with tx() as conn:
        conn.execute(f"UPDATE jobs SET {sets}, updated_at=now() WHERE id=%s", (*vals, job_id))


# ------------------------------------------------------------------ etapas
def step_download(job: dict) -> str:
    if not job["source_path"] or not (settings().media_dir / job["source_path"]).exists():
        update(job["id"], **source.download(job["id"], job["url"]))
    return "DOWNLOADED"


def step_transcribe(job: dict) -> str:
    if job["transcript"]:
        return "TRANSCRIBED"
    got = source.youtube_transcript(job["id"])
    if got:
        src, words = got
    else:
        log.info("job %s: sem legenda no YouTube, transcrevendo com whisper", job["id"])
        words = source.whisper_transcript(job["id"], settings().media_dir / job["source_path"],
                                          job["source_language"])
        src = f"whisper:{settings().whisper_model}"
    if len(words) < 20:
        raise StepFailed("transcrição vazia ou curta demais")
    update(job["id"], transcript=words, transcript_source=src)
    return "TRANSCRIBED"


def step_plan(job: dict) -> str:
    pending = job.get("pending_request") or {}
    kind = pending.get("kind") or ("initial" if not job["plan"] else "replan")
    p = planner.make_plan(job, mode=kind, request=pending.get("text"))
    version = job["plan_version"] + 1
    with tx() as conn:
        conn.execute("UPDATE jobs SET plan=%s, plan_version=%s, pending_request=NULL, updated_at=now() WHERE id=%s",
                     (Jsonb(p), version, job["id"]))
        conn.execute("INSERT INTO job_plans (job_id, version, kind, request, plan) VALUES (%s,%s,%s,%s,%s)"
                     " ON CONFLICT (job_id, version) DO UPDATE SET plan=EXCLUDED.plan",
                     (job["id"], version, kind, pending.get("text"), Jsonb(p)))
        # revisão pós-vídeo vai direto para renderização (o pedido já é a aprovação)
        if kind == "revision" or (job["options"] or {}).get("auto_approve"):
            conn.execute("UPDATE jobs SET approved_at=now() WHERE id=%s", (job["id"],))
            return "APPROVED"
    return "AWAITING_APPROVAL"


def step_render(job: dict) -> str:
    s = settings()
    r = planner.resolve_render(job)
    preset_name, style = subtitle_style(r.get("subtitle_preset"))
    d = source.job_dir(job["id"]) / f"render_v{job['plan_version']}"
    d.mkdir(exist_ok=True)
    res = cut.render(s.media_dir / job["source_path"], job["plan"]["segments"], job["transcript"], d,
                     hook_text=job["plan"].get("hook_text", ""), layout=r["layout"], opts=r,
                     subtitle_style=style, edits=job["plan"].get("edits") or [])
    out = str(res["path"].relative_to(s.media_dir))
    update(job["id"], output_path=out, output_duration_s=round(res["duration"], 2),
           qc_report={"render": {"layout": res["layout"], "subtitle_preset": preset_name,
                                 "subtitle_events": res["subtitle_events"],
                                 "preview_path": str(res["preview"].relative_to(s.media_dir)),
                                 "effect_warnings": res["effect_warnings"]}})
    with tx() as conn:
        conn.execute("UPDATE job_plans SET output_path=%s WHERE job_id=%s AND version=%s",
                     (out, job["id"], job["plan_version"]))
    return "RENDERED"


def step_qc(job: dict) -> str:
    report = cut.qc(settings().media_dir / job["output_path"],
                    (job["qc_report"] or {}).get("render", {}).get("subtitle_events", 0))
    report["render"] = (job["qc_report"] or {}).get("render")
    update(job["id"], qc_report=report)
    return "DONE" if report["passed"] else "QC_FAILED"


STEPS = {
    "QUEUED": step_download,
    "DOWNLOADED": step_transcribe,
    "TRANSCRIBED": step_plan,
    "APPROVED": step_render,
    "RENDERED": step_qc,
}


# ------------------------------------------------------------------ fila
def transition(conn, job_id: int, frm: str | None, to: str, note: str | None = None, **extra) -> None:
    sets = "".join(f", {k}=%s" for k in extra)
    vals = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in extra.values()]
    conn.execute(f"UPDATE jobs SET state=%s, updated_at=now(){sets} WHERE id=%s", (to, *vals, job_id))
    conn.execute("INSERT INTO job_events (job_id, from_state, to_state, note) VALUES (%s,%s,%s,%s)",
                 (job_id, frm, to, note))


def claim() -> dict | None:
    with tx() as conn:
        return conn.execute(
            f"""UPDATE jobs SET locked_until = now() + interval '{LEASE}', attempts = attempts + 1, updated_at = now()
                WHERE id = (SELECT id FROM jobs WHERE state = ANY(%s) AND next_run_at <= now()
                              AND (locked_until IS NULL OR locked_until < now())
                            ORDER BY next_run_at FOR UPDATE SKIP LOCKED LIMIT 1)
                RETURNING id, state, attempts, max_attempts""",
            (list(STEPS),)).fetchone()


def run_one() -> bool:
    job = claim()
    if not job:
        return False
    jid, state = job["id"], job["state"]
    log.info("job %s: %s (tentativa %s)", jid, state, job["attempts"])
    t0 = time.monotonic()
    try:
        to = STEPS[state](load(jid))
        note = f"ok em {time.monotonic() - t0:.1f}s"
        with tx() as conn:
            transition(conn, jid, state, to, note, attempts=0, locked_until=None, last_error=None)
    except Exception as e:  # noqa: BLE001
        log.exception("job %s falhou em %s", jid, state)
        permanent = isinstance(e, StepFailed) or job["attempts"] >= job["max_attempts"]
        with tx() as conn:
            if permanent:
                transition(conn, jid, state, "FAILED", repr(e)[:1000], failed_state=state,
                           locked_until=None, last_error=repr(e)[:4000])
            else:
                conn.execute("UPDATE jobs SET locked_until=NULL, last_error=%s, updated_at=now(),"
                             " next_run_at = now() + make_interval(mins => %s) WHERE id=%s",
                             (repr(e)[:4000], 4 ** (job["attempts"] - 1), jid))
    return True


RENDER_KEYS = ("layout", "crop_x", "top_box", "bottom_box", "subtitle_preset")


def act(job_id: int, action: str, body: dict) -> dict:
    res = _act(job_id, action, body)
    res.pop("_from")
    return res


def _act(job_id: int, action: str, body: dict) -> dict:
    """Ações manuais: approve, replan, revise, rerender, retry, cancel."""
    with tx() as conn:
        j = conn.execute("SELECT state, failed_state, options FROM jobs WHERE id=%s FOR UPDATE", (job_id,)).fetchone()
        if not j:
            raise KeyError(job_id)
        st = j["state"]
        text = (body.get("text") or body.get("feedback") or body.get("request") or "").strip()
        if action == "revise":  # alteração pedida depois do vídeo pronto
            if st not in ("DONE", "QC_FAILED"):
                raise ValueError(f"alterações só depois do vídeo pronto (estado atual {st})")
            if not text:
                raise ValueError("descreva a alteração em 'text'")
            transition(conn, job_id, st, "TRANSCRIBED", f"revisão: {text}"[:500], attempts=0,
                       pending_request={"kind": "revision", "text": text})
            return {"id": job_id, "state": "TRANSCRIBED", "_from": st}
        if action == "approve":
            if st != "AWAITING_APPROVAL":
                raise ValueError(f"não dá para aprovar no estado {st}")
            opts = {**(j["options"] or {}), **{k: body[k] for k in RENDER_KEYS if k in body}}
            transition(conn, job_id, st, "APPROVED", body.get("note"), options=opts)
            conn.execute("UPDATE jobs SET approved_at=now() WHERE id=%s", (job_id,))
            to = "APPROVED"
        elif action == "replan":  # novo roteiro antes de aprovar (com um pedido)
            if st not in ("AWAITING_APPROVAL", "DONE", "QC_FAILED"):
                raise ValueError(f"não dá para refazer o plano no estado {st}")
            transition(conn, job_id, st, "TRANSCRIBED", f"replan: {text}"[:500], attempts=0,
                       pending_request={"kind": "replan", "text": text})
            to = "TRANSCRIBED"
        elif action == "rerender":  # renderiza de novo (ex.: outro layout) sem refazer o plano
            if st not in ("DONE", "QC_FAILED"):
                raise ValueError(f"não dá para re-renderizar no estado {st}")
            opts = {**(j["options"] or {}), **{k: body[k] for k in RENDER_KEYS if k in body}}
            transition(conn, job_id, st, "APPROVED", "rerender", options=opts, attempts=0)
            to = "APPROVED"
        elif action == "retry":
            if st != "FAILED":
                raise ValueError(f"retry só em FAILED (estado atual {st})")
            to = j["failed_state"] or "QUEUED"
            transition(conn, job_id, st, to, "retry manual", attempts=0, failed_state=None, last_error=None,
                       locked_until=None)
        elif action == "cancel":
            to = "CANCELLED"
            transition(conn, job_id, st, to, body.get("note"))
        else:
            raise LookupError(action)
    return {"id": job_id, "state": to, "_from": st}


class Loop:
    def __init__(self, concurrency: int = 1) -> None:
        self.stop = threading.Event()
        self.threads = [threading.Thread(target=self._run, daemon=True) for _ in range(concurrency)]

    def start(self) -> None:
        for t in self.threads:
            t.start()

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                if not run_one():
                    self.stop.wait(2)
            except Exception:  # noqa: BLE001
                log.exception("erro no loop")
                self.stop.wait(10)
