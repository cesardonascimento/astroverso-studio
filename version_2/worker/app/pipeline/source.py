"""Download do vídeo e obtenção da transcrição com tempo por palavra.

Ordem de preferência da transcrição:
  1. legenda MANUAL do YouTube no idioma do vídeo   (texto melhor; tempo por frase → distribuímos por palavra)
  2. legenda AUTOMÁTICA do YouTube (faixa original)  (tempo por palavra nativo)
  3. Whisper local (faster-whisper)                  (quando não há legenda)
Para a legenda queimada no vídeo precisamos de tempo por palavra; por isso a automática costuma ser
preferível à manual quando ambas existem (a manual entra como texto de referência para o LLM).
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx
import yt_dlp

from ..config import settings
from ..db import record_generation

log = logging.getLogger(__name__)


def job_dir(job_id: int) -> Path:
    d = settings().media_dir / "jobs" / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ydl_opts(**extra) -> dict:
    opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "noprogress": True}
    if settings().youtube_cookies_file:
        opts["cookiefile"] = settings().youtube_cookies_file
    opts.update(extra)
    return opts


# ------------------------------------------------------------------ download
def download(job_id: int, url: str) -> dict:
    d = job_dir(job_id)
    t0 = time.monotonic()
    opts = _ydl_opts(
        format="bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
        merge_output_format="mp4",
        outtmpl=str(d / "source.%(ext)s"),
        writeinfojson=False,
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        info = ydl.sanitize_info(info)
    path = next(d.glob("source.mp4"), None) or next(d.glob("source.*"))
    (d / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    record_generation(step="download", provider="yt-dlp", job_id=job_id, units=info.get("duration"),
                      cost_usd=0, ok=True, duration_ms=int((time.monotonic() - t0) * 1000))
    return {
        "source_id": info.get("id"),
        "source_title": info.get("title"),
        "source_channel": info.get("channel") or info.get("uploader"),
        "source_channel_url": info.get("channel_url") or info.get("uploader_url"),
        "source_duration_s": info.get("duration"),
        "source_language": info.get("language"),
        "source_path": str(path.relative_to(settings().media_dir)),
    }


# ------------------------------------------------------------------ transcrição
def _pick_track(tracks: dict, lang: str | None, auto: bool) -> tuple[str, str] | None:
    """Escolhe a faixa de legenda e devolve (código, url json3)."""
    if not tracks:
        return None
    base = (lang or "pt").split("-")[0].lower()
    keys = list(tracks)
    if auto:
        # faixa original do reconhecimento automático vem como "<lang>-orig"; as outras são traduções
        prefs = [k for k in keys if k.lower().endswith("-orig") and k.lower().startswith(base)]
        prefs += [k for k in keys if k.lower().endswith("-orig")]
        prefs += [k for k in keys if k.lower() in (base, f"{base}-br")]
    else:
        prefs = [k for k in keys if k.lower().split("-")[0] == base]
    for k in prefs:
        fmt = next((f for f in tracks[k] if f.get("ext") == "json3"), None)
        if fmt:
            return k, fmt["url"]
    return None


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", t.replace("\n", " ")).strip()


def is_marker(token: str) -> bool:
    """Marcas que não são fala: '>>' (troca de locutor na legenda automática), '-' solto etc."""
    return token in (">>", ">", "-", "–", "—", "&gt;&gt;") or not any(c.isalnum() for c in token)


def parse_json3(data: dict) -> list[dict]:
    """json3 do YouTube → [{"w","s","e"}]. Usa o offset por palavra quando existe (legenda automática);
    senão distribui o tempo do trecho entre as palavras proporcionalmente ao tamanho."""
    words: list[dict] = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs or "tStartMs" not in ev:
            continue
        start = ev["tStartMs"] / 1000
        dur = ev.get("dDurationMs", 0) / 1000
        pieces = [(s.get("utf8", ""), s.get("tOffsetMs")) for s in segs]
        if len(pieces) > 1 and any(off is not None for _, off in pieces[1:]):
            for i, (txt, off) in enumerate(pieces):
                txt = _clean(txt)
                if not txt or txt.startswith("["):  # [Música], [Aplausos]
                    continue
                s = start + (off or 0) / 1000
                for w in txt.split():
                    if is_marker(w):
                        continue
                    words.append({"w": w, "s": round(s, 3), "e": None})
        else:
            txt = _clean("".join(p for p, _ in pieces))
            if not txt or (txt.startswith("[") and txt.endswith("]")):
                continue
            toks = [t for t in txt.split() if not is_marker(t)]
            total = sum(len(t) + 1 for t in toks)
            t = start
            for tok in toks:
                span = dur * (len(tok) + 1) / total if total else 0
                words.append({"w": tok, "s": round(t, 3), "e": round(t + span, 3)})
                t += span
    # fecha os finais faltantes com o início da próxima palavra (máx. 1s de duração)
    for i, w in enumerate(words):
        if w["e"] is None:
            nxt = words[i + 1]["s"] if i + 1 < len(words) else w["s"] + 0.5
            w["e"] = round(min(nxt, w["s"] + 1.0), 3)
    return words


def youtube_transcript(job_id: int) -> tuple[str, list[dict]] | None:
    info = json.loads((job_dir(job_id) / "info.json").read_text(encoding="utf-8"))
    lang = info.get("language")
    choices = [
        ("youtube_auto", _pick_track(info.get("automatic_captions") or {}, lang, auto=True)),
        ("youtube_manual", _pick_track(info.get("subtitles") or {}, lang, auto=False)),
    ]
    for source, pick in choices:
        if not pick:
            continue
        code, url = pick
        try:
            r = httpx.get(url, timeout=60)
            r.raise_for_status()
            words = parse_json3(r.json())
        except Exception:  # noqa: BLE001
            log.warning("falha ao baixar legenda %s (%s)", source, code, exc_info=True)
            continue
        if len(words) > 20:
            (job_dir(job_id) / f"transcript_{source}_{code}.json").write_text(
                json.dumps(words, ensure_ascii=False), encoding="utf-8")
            return f"{source}:{code}", words
    return None


def whisper_transcript(job_id: int, source: Path, language: str | None) -> list[dict]:
    from faster_whisper import WhisperModel

    s = settings()
    t0 = time.monotonic()
    audio = job_dir(job_id) / "audio16k.wav"
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-ac", "1", "-ar", "16000", str(audio)],
                   check=True)
    model = WhisperModel(s.whisper_model, device=s.whisper_device,
                         compute_type="int8" if s.whisper_device == "cpu" else "float16")
    segments, _ = model.transcribe(str(audio), language=(language or "pt").split("-")[0],
                                   word_timestamps=True, vad_filter=True)
    words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
             for seg in segments for w in (seg.words or []) if w.word.strip()]
    audio.unlink(missing_ok=True)
    record_generation(step="transcribe", provider="faster-whisper", model=s.whisper_model, job_id=job_id,
                      units=len(words), cost_usd=0, ok=True, duration_ms=int((time.monotonic() - t0) * 1000))
    return words


def transcript_lines(words: list[dict], max_words: int = 14) -> list[dict]:
    """Agrupa palavras em linhas curtas (quebra em pontuação/pausa) para o LLM ler com timestamps."""
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        pause = i + 1 < len(words) and words[i + 1]["s"] - w["e"] > 0.6
        if len(cur) >= max_words or re.search(r"[.!?]$", w["w"]) or pause:
            lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
    if cur:
        lines.append({"s": cur[0]["s"], "e": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
    return lines
