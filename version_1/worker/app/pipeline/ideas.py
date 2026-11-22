"""Geração e ranking de ideias a partir dos temas do snapshot mais recente."""
from __future__ import annotations

import json

from psycopg.types.json import Jsonb

from ..config import settings
from ..db import tx
from ..llm import llm, load_prompt
from ..schemas import IdeaBatch
from ..scoring import score_idea


def active_insights(conn) -> str:
    rows = conn.execute("SELECT content FROM insights WHERE active ORDER BY created_at DESC LIMIT 20").fetchall()
    if not rows:
        return ""
    return "Aprendizados dos vídeos anteriores (dados reais de performance):\n" + "\n".join(
        f"- {r['content']}" for r in rows)


def generate(count: int = 20, snapshot_id: int | None = None, min_fit: int = 4) -> list[dict]:
    with tx() as conn:
        if snapshot_id is None:
            row = conn.execute(
                "SELECT snapshot_id FROM trend_themes ORDER BY created_at DESC LIMIT 1").fetchone()
            if not row:
                raise RuntimeError("nenhum tema de tendência ainda — rode /trends/refresh primeiro")
            snapshot_id = row["snapshot_id"]
        themes = conn.execute(
            "SELECT id, theme, description, related_hashtags, momentum, content_angles, fit_score, risk_notes"
            " FROM trend_themes WHERE snapshot_id=%s AND coalesce(fit_score,0) >= %s ORDER BY fit_score DESC",
            (snapshot_id, min_fit),
        ).fetchall()
        past = conn.execute(
            "SELECT title, hook FROM ideas WHERE status IN ('selected','produced') OR created_at > now() - interval '30 days'"
            " ORDER BY created_at DESC LIMIT 80").fetchall()
        insights = active_insights(conn)
    if not themes:
        raise RuntimeError("nenhum tema com encaixe suficiente neste snapshot")

    version, system = load_prompt("ideas")
    system = system.replace("{insights}", insights)
    user = (
        f"Gere {count} ideias em {settings().content_language}.\n\n"
        "TEMAS EM ALTA:\n" + json.dumps([{k: t[k] for k in t if k != "id"} for t in themes],
                                        ensure_ascii=False, default=str)
        + "\n\nIDEIAS JÁ FEITAS OU PROPOSTAS (não repetir):\n"
        + ("\n".join(f"- {p['title']} | {p['hook']}" for p in past) or "(nenhuma)")
    )
    batch = llm().structured(step="ideas", system=system, user=user, output=IdeaBatch,
                             ctx={"snapshot_id": snapshot_id})

    theme_ids = {t["theme"].strip().lower(): t["id"] for t in themes}
    out = []
    with tx() as conn:
        for idea in batch.ideas:
            sim = conn.execute(
                "SELECT coalesce(max(greatest(similarity(title, %s), similarity(hook, %s))), 0) AS s FROM ideas",
                (idea.title, idea.hook),
            ).fetchone()["s"]
            final, breakdown, rejected = score_idea(idea.scores.model_dump(), float(sim))
            breakdown["risk_notes"] = idea.risk_notes
            row = conn.execute(
                "INSERT INTO ideas (theme_id, title, hook, angle, format, why_now, related_hashtags, language,"
                " target_duration_s, scores, similarity_max, final_score, score_breakdown, status, model, prompt_version)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (theme_ids.get(idea.theme.strip().lower()), idea.title, idea.hook, idea.angle, idea.format,
                 idea.why_now, [h.lstrip("#") for h in idea.related_hashtags], settings().content_language,
                 idea.target_duration_s, Jsonb(idea.scores.model_dump()), round(float(sim), 3), final,
                 Jsonb(breakdown), "auto_rejected" if rejected else "proposed", settings().llm_model, version),
            ).fetchone()
            out.append({"id": row["id"], "final_score": final, "auto_rejected": rejected,
                        "similarity": round(float(sim), 3), **idea.model_dump()})
    out.sort(key=lambda x: x["final_score"], reverse=True)
    return out
