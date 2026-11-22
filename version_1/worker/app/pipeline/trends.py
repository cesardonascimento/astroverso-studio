"""Trend Discovery: busca tendências → grava snapshot → LLM agrupa em temas."""
from __future__ import annotations

import json
import logging

from psycopg.types.json import Jsonb

from ..config import settings
from ..db import tx
from ..llm import llm, load_prompt
from ..providers.trends import trend_source
from ..schemas import TrendAnalysis

log = logging.getLogger(__name__)


def refresh(country: str | None = None, period_days: int = 7) -> dict:
    country = country or settings().trend_country
    fetch = trend_source().fetch(country, period_days)

    with tx() as conn:
        snap_id = conn.execute(
            "INSERT INTO trend_snapshots (source, country, period_days, raw) VALUES (%s,%s,%s,%s) RETURNING id",
            (fetch.source, country, period_days, Jsonb(fetch.raw)),
        ).fetchone()["id"]
        for it in fetch.items:
            conn.execute(
                "INSERT INTO trends (snapshot_id, kind, name, rank, posts, views, direction, industries, country, data)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (snap_id, it.kind, it.name, it.rank, it.posts, it.views, it.direction,
                 it.industries, it.country, Jsonb(it.data)),
            )

    themes = analyze(snap_id)
    return {"snapshot_id": snap_id, "source": fetch.source, "items": len(fetch.items), "themes": themes}


def analyze(snapshot_id: int) -> list[dict]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT kind, name, rank, posts, views, direction, industries, country FROM trends"
            " WHERE snapshot_id=%s ORDER BY kind, rank NULLS LAST",
            (snapshot_id,),
        ).fetchall()
    if not rows:
        raise RuntimeError("snapshot sem tendências")

    hashtags = [r for r in rows if r["kind"] != "video"]
    videos = [r for r in rows if r["kind"] == "video"]
    user = (
        f"Hashtags em alta ({rows[0]['country'] or settings().trend_country}, últimos dias):\n"
        + json.dumps(hashtags, ensure_ascii=False, default=str)
    )
    if videos:
        user += (
            "\n\nVídeos orgânicos com mais engajamento nos EUA (use só como referência de FORMATO/ESTILO, "
            "não de assunto):\n" + json.dumps(videos, ensure_ascii=False, default=str)
        )

    version, system = load_prompt("trend_analysis")
    s = settings()
    result = llm().structured(
        step="trend_analysis", system=system, user=user, output=TrendAnalysis,
        web_search=5 if s.llm_trend_web_search else 0, ctx={"snapshot_id": snapshot_id},
    )

    out = []
    with tx() as conn:
        for t in result.themes:
            tid = conn.execute(
                "INSERT INTO trend_themes (snapshot_id, theme, description, related_hashtags, momentum,"
                " content_angles, fit_score, risk_notes, model, prompt_version)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (snapshot_id, t.theme, t.description, [h.lstrip("#") for h in t.related_hashtags], t.momentum,
                 Jsonb(t.content_angles), t.fit_score, t.risk_notes, s.llm_model, version),
            ).fetchone()["id"]
            out.append({"id": tid, **t.model_dump()})
    return out
