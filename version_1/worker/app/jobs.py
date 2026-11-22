"""Fila de jobs em cima do próprio Postgres (sem Redis).

- Um vídeo é "trabalhável" quando seu estado tem uma etapa associada.
- O worker pega um vídeo com SELECT ... FOR UPDATE SKIP LOCKED e grava um lease (locked_until).
  Se o processo morrer no meio, o lease expira e outro ciclo retoma de onde parou.
- Falha → backoff exponencial (1, 4, 16 min). Esgotou tentativas → FAILED (failed_state guarda onde parou).
"""
from __future__ import annotations

import logging
import threading
import time

from .db import tx
from .pipeline import production as p

log = logging.getLogger(__name__)

STEPS = {
    "QUEUED": (p.step_script, "SCRIPTED"),
    "SCRIPTED": (p.step_voice, "VOICED"),
    "VOICED": (p.step_visuals, "VISUALS_READY"),
    "VISUALS_READY": (p.step_render, "RENDERED"),
    "RENDERED": (p.step_qc, None),  # QC decide o próximo estado
}
LEASE = "20 minutes"

# transições manuais permitidas (API / n8n)
MANUAL = {
    "approve": ({"READY_FOR_REVIEW"}, "APPROVED"),
    "reject": ({"READY_FOR_REVIEW", "QC_FAILED"}, "REJECTED"),
    "cancel": (set(STEPS) | {"READY_FOR_REVIEW", "QC_FAILED", "FAILED"}, "CANCELLED"),
}


def transition(conn, video_id: int, frm: str | None, to: str, note: str | None = None, **extra) -> None:
    sets = ", ".join(f"{k}=%s" for k in extra)
    conn.execute(
        f"UPDATE videos SET state=%s, updated_at=now(){', ' + sets if sets else ''} WHERE id=%s",
        (to, *extra.values(), video_id),
    )
    conn.execute("INSERT INTO video_events (video_id, from_state, to_state, note) VALUES (%s,%s,%s,%s)",
                 (video_id, frm, to, note))


def claim() -> dict | None:
    with tx() as conn:
        return conn.execute(
            f"""
            UPDATE videos SET locked_until = now() + interval '{LEASE}', attempts = attempts + 1, updated_at = now()
            WHERE id = (
              SELECT id FROM videos
              WHERE state = ANY(%s) AND next_run_at <= now()
                AND (locked_until IS NULL OR locked_until < now())
              ORDER BY next_run_at
              FOR UPDATE SKIP LOCKED LIMIT 1)
            RETURNING id, state, attempts, max_attempts
            """,
            (list(STEPS),),
        ).fetchone()


def run_one() -> bool:
    job = claim()
    if not job:
        return False
    vid, state = job["id"], job["state"]
    fn, nxt = STEPS[state]
    log.info("video %s: %s (tentativa %s)", vid, state, job["attempts"])
    t0 = time.monotonic()
    try:
        result = fn(p.load(vid))
        to = result if nxt is None else nxt
        with tx() as conn:
            transition(conn, vid, state, to, f"ok em {time.monotonic() - t0:.1f}s",
                       attempts=0, locked_until=None, last_error=None)
    except Exception as e:  # noqa: BLE001
        log.exception("video %s falhou em %s", vid, state)
        permanent = isinstance(e, p.StepFailed) or job["attempts"] >= job["max_attempts"]
        with tx() as conn:
            if permanent:
                transition(conn, vid, state, "FAILED", repr(e)[:1000], failed_state=state,
                           locked_until=None, last_error=repr(e)[:4000])
            else:
                backoff = 4 ** (job["attempts"] - 1)  # 1, 4, 16 min
                conn.execute(
                    "UPDATE videos SET locked_until=NULL, last_error=%s,"
                    " next_run_at = now() + make_interval(mins => %s), updated_at=now() WHERE id=%s",
                    (repr(e)[:4000], backoff, vid))
    return True


def retry(video_id: int) -> dict:
    """Retoma um vídeo FAILED/QC_FAILED a partir da etapa onde parou (ou do zero com script novo)."""
    with tx() as conn:
        v = conn.execute("SELECT state, failed_state FROM videos WHERE id=%s FOR UPDATE", (video_id,)).fetchone()
        if not v:
            raise KeyError(video_id)
        if v["state"] == "FAILED":
            back = v["failed_state"] or "QUEUED"
        elif v["state"] == "QC_FAILED":
            back = "VISUALS_READY"  # re-renderiza
        else:
            raise ValueError(f"não dá para reprocessar a partir de {v['state']}")
        if back == "QUEUED":
            conn.execute("UPDATE videos SET script_id=NULL WHERE id=%s", (video_id,))  # roteiro novo
        transition(conn, video_id, v["state"], back, "retry manual",
                   attempts=0, failed_state=None, last_error=None, locked_until=None)
    return {"id": video_id, "state": back}


def manual(video_id: int, action: str, note: str | None = None) -> dict:
    allowed, to = MANUAL[action]
    with tx() as conn:
        v = conn.execute("SELECT state FROM videos WHERE id=%s FOR UPDATE", (video_id,)).fetchone()
        if not v:
            raise KeyError(video_id)
        if v["state"] not in allowed:
            raise ValueError(f"'{action}' não permitido no estado {v['state']}")
        transition(conn, video_id, v["state"], to, note)
    return {"id": video_id, "state": to}


class Loop:
    def __init__(self, concurrency: int = 1) -> None:
        self.stop = threading.Event()
        self.threads = [threading.Thread(target=self._run, name=f"job-{i}", daemon=True) for i in range(concurrency)]

    def start(self) -> None:
        for t in self.threads:
            t.start()

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                if not run_one():
                    self.stop.wait(3)
            except Exception:  # noqa: BLE001 — o loop nunca morre
                log.exception("erro no loop de jobs")
                self.stop.wait(10)
