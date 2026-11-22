"""Quality Control técnico + de conteúdo. Cada regra vira um item no relatório."""
from __future__ import annotations

from .config import settings
from .render import ffmpeg

MIN_S, MAX_S = 8, 90  # nosso alvo editorial (o TikTok aceita vídeos bem mais longos)
MAX_BYTES = 287 * 1024 * 1024  # bem abaixo do limite do TikTok; vídeo de 60s fica ~20-60MB


def check_video(v: dict) -> dict:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail=None, severity: str = "error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "severity": severity})

    path = settings().media_dir / (v.get("output_path") or "missing")
    add("file_exists", path.exists(), str(path))
    if path.exists():
        info = ffmpeg.probe(path)
        vs = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        aus = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        dur = float(info["format"]["duration"])
        size = int(info["format"]["size"])
        add("duration", MIN_S <= dur <= MAX_S, round(dur, 2))
        add("size", size <= MAX_BYTES, size)
        add("video_stream", vs is not None)
        add("audio_stream", aus is not None)
        if vs:
            fps_n, fps_d = (int(x) for x in vs["r_frame_rate"].split("/"))
            add("resolution_1080x1920", (vs["width"], vs["height"]) == (1080, 1920), f"{vs['width']}x{vs['height']}")
            add("codec_h264", vs["codec_name"] == "h264", vs["codec_name"])
            add("pix_fmt_yuv420p", vs.get("pix_fmt") == "yuv420p", vs.get("pix_fmt"))
            add("fps_30", abs(fps_n / fps_d - 30) < 0.01, vs["r_frame_rate"])
        if aus:
            add("codec_aac", aus["codec_name"] == "aac", aus["codec_name"])

        scan = ffmpeg.scan_content(path)
        add("no_decode_errors", not scan["decode_errors"] and scan["returncode"] == 0, scan["decode_errors"])
        add("no_black_screen", scan["black_total_s"] < 1.0, scan["black_total_s"])
        add("no_long_silence", scan["silence_total_s"] < 2.0, scan["silence_total_s"], severity="warning")

    # legendas
    from .pipeline.production import assets
    subs = assets(v["id"], "subtitle").get(-1)
    add("subtitles_present", bool(subs and subs["meta"].get("events", 0) > 0),
        subs["meta"] if subs else None)

    # conteúdo (revisão do roteiro feita na etapa de script)
    script = v.get("script") or {}
    review = script.get("review") or {}
    add("script_review_approved", review.get("approved", False), review.get("issues"))
    low_conf = [c["claim"] for c in (script.get("content") or {}).get("fact_claims", []) if c["confidence"] == "low"]
    add("no_low_confidence_facts", not low_conf, low_conf, severity="warning")

    passed = all(c["ok"] for c in checks if c["severity"] == "error")
    return {"passed": passed, "checks": checks}
