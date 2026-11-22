"""Avisa o n8n a cada mudança de estado de um job (webhook). Nunca bloqueia nem derruba o pipeline:
roda numa thread, tenta algumas vezes e desiste com log. O n8n decide o que fazer (Discord etc.)."""
from __future__ import annotations

import json
import logging
import threading
import time
from decimal import Decimal

import httpx

from .config import settings
from .db import tx

log = logging.getLogger(__name__)


def payload(job_id: int, frm: str | None, to: str, note: str | None) -> dict:
    with tx() as conn:
        j = conn.execute(
            "SELECT id, url, state, source_title, source_channel, instructions, context, plan_version,"
            " plan->>'title' AS title, plan->>'changes' AS changes, plan->>'caption' AS caption,"
            " plan->'hashtags' AS hashtags, (plan->>'duration_s')::numeric AS plan_duration_s,"
            " output_path, output_duration_s, qc_report->'render'->>'preview_path' AS preview_path,"
            " qc_report->>'passed' AS qc_passed, last_error FROM jobs WHERE id=%s", (job_id,)).fetchone()
    body = {"event": "job.state_changed", "job_id": job_id, "from": frm, "to": to, "note": note, "job": j}
    # Decimal / datetime do Postgres → tipos JSON
    return json.loads(json.dumps(body, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)))


def _send(body: dict) -> None:
    url = settings().n8n_events_url
    for attempt in range(4):
        try:
            r = httpx.post(url, json=body, timeout=15,
                           headers={"X-Worker-Token": settings().worker_token})
            if r.status_code < 300:
                return
            log.warning("n8n respondeu %s ao evento do job %s", r.status_code, body["job_id"])
        except Exception as e:  # noqa: BLE001
            log.warning("falha ao avisar n8n (tentativa %s): %s", attempt + 1, e)
        time.sleep(2 ** attempt)


def notify(job_id: int, frm: str | None, to: str, note: str | None = None) -> None:
    if not settings().n8n_events_url:
        return
    try:
        body = payload(job_id, frm, to, note)
    except Exception:  # noqa: BLE001
        log.exception("falha ao montar evento do job %s", job_id)
        return
    threading.Thread(target=_send, args=(body,), daemon=True).start()
