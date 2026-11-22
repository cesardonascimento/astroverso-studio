"""Etapas de produção. Cada etapa é idempotente: se o artefato já existe, reaproveita.

QUEUED → [script] → SCRIPTED → [voice] → VOICED → [visuals] → VISUALS_READY
       → [render] → RENDERED → [qc] → READY_FOR_REVIEW | QC_FAILED
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from psycopg.types.json import Jsonb

from ..config import settings
from ..db import tx
from ..llm import llm, load_prompt
from ..pipeline.ideas import active_insights
from ..providers.images import image_provider
from ..providers.tts import Word, tts_provider
from ..render import ffmpeg
from ..render.subtitles import build_ass
from ..schemas import Script, ScriptReview

log = logging.getLogger(__name__)


# ~2,7 palavras/s é o ritmo de narração rápida em pt-BR com TTS_RATE=+12% (medido: ~2,5-2,9)
WORDS_PER_SECOND = 2.7


class StepFailed(RuntimeError):
    """Falha que não adianta repetir (ex.: roteiro reprovado na revisão)."""


def video_dir(video_id: int) -> Path:
    d = settings().media_dir / "videos" / str(video_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def rel(p: Path) -> str:
    return str(p.relative_to(settings().media_dir))


def load(video_id: int) -> dict:
    with tx() as conn:
        v = conn.execute(
            "SELECT v.*, i.title, i.hook, i.angle, i.format, i.why_now, i.target_duration_s, i.related_hashtags"
            " FROM videos v JOIN ideas i ON i.id = v.idea_id WHERE v.id=%s", (video_id,)).fetchone()
        if v and v["script_id"]:
            v["script"] = conn.execute("SELECT * FROM scripts WHERE id=%s", (v["script_id"],)).fetchone()
        return v


def save_asset(conn, video_id: int, kind: str, scene: int, path: Path, provider: str, meta: dict) -> None:
    conn.execute(
        "INSERT INTO video_assets (video_id, kind, scene_index, path, provider, meta) VALUES (%s,%s,%s,%s,%s,%s)"
        " ON CONFLICT (video_id, kind, scene_index) DO UPDATE SET path=EXCLUDED.path, provider=EXCLUDED.provider,"
        " meta=EXCLUDED.meta, created_at=now()",
        (video_id, kind, scene, rel(path), provider, Jsonb(meta)),
    )


def assets(video_id: int, kind: str) -> dict[int, dict]:
    with tx() as conn:
        rows = conn.execute("SELECT * FROM video_assets WHERE video_id=%s AND kind=%s", (video_id, kind)).fetchall()
    return {r["scene_index"]: r for r in rows}


# ---------------------------------------------------------------- script
def step_script(v: dict) -> None:
    if v["script_id"]:
        return
    s = settings()
    ctx = {"video_id": v["id"], "idea_id": v["idea_id"]}
    with tx() as conn:
        insights = active_insights(conn)
    version, system = load_prompt("script")
    system = system.replace("{insights}", insights)
    idea = {k: v[k] for k in ("title", "hook", "angle", "format", "why_now", "target_duration_s", "related_hashtags")}
    target_s = max(15, min(60, v["target_duration_s"] or 30))
    max_words = int(target_s * WORDS_PER_SECOND)
    script = llm().structured(
        step="script", system=system, ctx=ctx, output=Script,
        user=(f"Escreva o roteiro em {s.content_language} para esta ideia. Duração alvo: {target_s}s "
              f"(máximo {max_words} palavras de narração no total).\n{json.dumps(idea, ensure_ascii=False)}"),
    )

    rv_version, rv_system = load_prompt("script_review")

    def review_of(sc: Script) -> ScriptReview:
        return llm().structured(
            step="script_review", system=rv_system, ctx=ctx, output=ScriptReview, model=s.llm_model_fast,
            user=json.dumps(sc.model_dump(), ensure_ascii=False),
        )

    review = review_of(script)
    words = narration_words(script.model_dump())
    # uma rodada de reescrita: aplica as correções da revisão e corta para o tamanho
    if review.issues or not review.approved or words > max_words * 1.15:
        rev_version, rev_system = load_prompt("script_revise")
        script = llm().structured(
            step="script_revise", system=rev_system, ctx=ctx, output=Script,
            user=json.dumps({"limite_palavras": max_words, "palavras_atuais": words,
                             "roteiro": script.model_dump(), "revisao": review.model_dump()}, ensure_ascii=False),
        )
        version = f"{version}+{rev_version}"
        review = review_of(script)
        words = narration_words(script.model_dump())
        if words > max_words * 1.3:
            review.approved = False
            review.issues.append(f"roteiro longo demais após reescrita: {words} palavras (limite {max_words})")

    with tx() as conn:
        ver = conn.execute("SELECT coalesce(max(version),0)+1 AS n FROM scripts WHERE idea_id=%s",
                           (v["idea_id"],)).fetchone()["n"]
        sid = conn.execute(
            "INSERT INTO scripts (idea_id, version, content, caption, hashtags, review, model, prompt_version)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (v["idea_id"], ver, Jsonb(script.model_dump()), script.caption,
             [h.lstrip("#") for h in script.hashtags], Jsonb(review.model_dump()), s.llm_model,
             f"{version}+{rv_version}"),
        ).fetchone()["id"]
        conn.execute("UPDATE videos SET script_id=%s WHERE id=%s", (sid, v["id"]))
    if not review.approved:
        raise StepFailed(f"roteiro reprovado na revisão: {review.issues}")


def narration_words(script: dict) -> int:
    return sum(len(t.split()) for t in scene_texts(script))


# ---------------------------------------------------------------- voice
def scene_texts(script: dict) -> list[str]:
    scenes = [sc["narration"] for sc in script["scenes"]]
    norm = lambda t: "".join(ch for ch in t.lower() if ch.isalnum())  # noqa: E731
    last = norm(scenes[-1])
    # o LLM às vezes já põe o loop/CTA na última cena: não falar duas vezes
    tail = " ".join(x for x in (script.get("loop_line"), script.get("cta")) if x and norm(x) not in last)
    if tail:
        scenes[-1] = f"{scenes[-1]} {tail}"
    return scenes


def step_voice(v: dict) -> None:
    script = v["script"]["content"]
    d = video_dir(v["id"])
    done = assets(v["id"], "voice")
    tts = tts_provider()
    voice = v["settings"].get("voice")
    rate = v["settings"].get("rate")
    for i, text in enumerate(scene_texts(script)):
        if i in done and (settings().media_dir / done[i]["path"]).exists():
            continue
        out = d / f"voice_{i:02d}.mp3"
        res = tts.synthesize(text, out, voice=voice, rate=rate, ctx={"video_id": v["id"]})
        meta = {"voice": res.voice, "duration": ffmpeg.duration(out),
                "words": [w.__dict__ for w in res.words]}
        with tx() as conn:
            save_asset(conn, v["id"], "voice", i, out, res.provider, meta)


# ---------------------------------------------------------------- visuals
def step_visuals(v: dict) -> None:
    script = v["script"]["content"]
    d = video_dir(v["id"])
    done = assets(v["id"], "image")
    prov = image_provider()
    style = v["settings"].get("visual_style", "")
    for i, sc in enumerate(script["scenes"]):
        if i in done and (settings().media_dir / done[i]["path"]).exists():
            continue
        out = d / f"image_{i:02d}.jpg"
        prompt = f"{sc['visual_prompt']}. {style}".strip()
        meta = prov.get(prompt=prompt, query=sc["stock_query"], out=out, ctx={"video_id": v["id"]})
        with tx() as conn:
            save_asset(conn, v["id"], "image", i, out, prov.name, {**meta, "prompt": prompt})


# ---------------------------------------------------------------- render
def step_render(v: dict) -> None:
    media = settings().media_dir
    script = v["script"]["content"]
    d = video_dir(v["id"])
    voices, images = assets(v["id"], "voice"), assets(v["id"], "image")
    n = len(script["scenes"])
    if len(voices) < n or len(images) < n:
        raise RuntimeError("faltam assets de voz/imagem — etapa anterior incompleta")

    clips, audio_parts, words = [], [], []
    t = 0.0
    for i in range(n):
        vo = voices[i]
        seconds = float(vo["meta"]["duration"]) + (0.25 if i == n - 1 else 0.0)  # respiro no final
        clip = d / f"clip_{i:02d}.mp4"
        clip_len = ffmpeg.scene_clip(media / images[i]["path"], seconds, clip, zoom_in=(i % 2 == 0))
        clips.append(clip)
        audio_parts.append((media / vo["path"], clip_len))
        words += [Word(w["text"], w["start"] + t, w["end"] + t) for w in vo["meta"]["words"]]
        t += clip_len

    ffmpeg.concat_video(clips, d / "video_noaudio.mp4")
    ffmpeg.concat_audio(audio_parts, d / "narration.wav")
    subs = d / "subs.ass"
    n_events = build_ass(words, subs, hook_text=script.get("hook_text", ""), total_duration=t)
    final = d / "final.mp4"
    ffmpeg.final_encode(d / "video_noaudio.mp4", d / "narration.wav", subs, final)

    with tx() as conn:
        save_asset(conn, v["id"], "subtitle", -1, subs, "ass", {"events": n_events, "words": len(words)})
        save_asset(conn, v["id"], "render", -1, final, "ffmpeg", {})
        conn.execute("UPDATE videos SET output_path=%s, duration_s=%s WHERE id=%s",
                     (rel(final), round(ffmpeg.duration(final), 2), v["id"]))
    for c in clips:  # intermediários grandes
        c.unlink(missing_ok=True)


# ---------------------------------------------------------------- QC
def step_qc(v: dict) -> str:
    """Devolve o próximo estado: READY_FOR_REVIEW ou QC_FAILED."""
    from ..qc import check_video

    report = check_video(v)
    with tx() as conn:
        conn.execute("UPDATE videos SET qc_report=%s WHERE id=%s", (Jsonb(report), v["id"]))
    return "READY_FOR_REVIEW" if report["passed"] else "QC_FAILED"
