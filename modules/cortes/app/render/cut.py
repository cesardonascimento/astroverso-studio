"""Renderização do corte: segmentos → 9:16 → concatena → legendas + loudness → MP4 de entrega."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .subtitles import Word, build_ass

W, H, FPS = 1080, 1920, 30


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], cwd: Path | None = None) -> None:
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise FFmpegError(f"{args[0]} falhou ({p.returncode}): {p.stderr[-3000:]}")


def probe(path: Path) -> dict:
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(path)], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def video_size(path: Path) -> tuple[int, int]:
    vs = next(s for s in probe(path)["streams"] if s["codec_type"] == "video")
    return int(vs["width"]), int(vs["height"])


def _box(b: list[float]) -> str:
    """[x, y, w, h] normalizados (0-1) → filtro crop."""
    x, y, w, h = b
    return f"crop=iw*{w:.4f}:ih*{h:.4f}:iw*{x:.4f}:ih*{y:.4f}"


def layout_filter(layout: str, opts: dict, src_size: tuple[int, int]) -> tuple[str, int]:
    """Filtro de vídeo para 1080x1920 + posição vertical da legenda (MarginV do .ass).
    crop:     preenche a tela cortando as laterais (crop_x: 0 = esquerda, 0.5 = centro, 1 = direita)
    fit_blur: vídeo inteiro no meio + fundo desfocado (nunca corta ninguém)
    split:    duas regiões empilhadas (react/podcast): top_box em cima, bottom_box embaixo,
              cada uma [x, y, w, h] normalizado. A de baixo mantém a proporção; a de cima preenche o resto."""
    tail = f"setsar=1,fps={FPS},format=yuv420p"
    if layout == "crop":
        cx = float(opts.get("crop_x", 0.5))
        return f"[0:v]scale=-2:{H},crop={W}:{H}:(iw-{W})*{cx:.3f}:0,{tail}[v]", 640
    if layout == "fit_blur":
        return (
            f"[0:v]split[a][b];"
            f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:2,eq=brightness=-0.10[bg];"
            f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,{tail}[v]"
        ), 480
    if layout == "split":
        top = opts.get("top_box") or [0.25, 0.0, 0.5, 1.0]
        bot = opts.get("bottom_box")
        if not bot:
            raise ValueError("layout split precisa de bottom_box [x, y, w, h]")
        sw, sh = src_size
        bot_h = int(W * (bot[3] * sh) / (bot[2] * sw)) // 2 * 2
        bot_h = max(600, min(1100, bot_h))
        top_h = H - bot_h
        f = (
            f"[0:v]split[a][b];"
            f"[a]{_box(top)},scale={W}:{top_h}:force_original_aspect_ratio=increase,crop={W}:{top_h}[t];"
            f"[b]{_box(bot)},scale={W}:{bot_h}:force_original_aspect_ratio=increase,crop={W}:{bot_h}[d];"
            f"[t][d]vstack,{tail}[v]"
        )
        return f, max(0, H - top_h - 45)  # legenda centrada na divisão
    raise ValueError(f"layout desconhecido: {layout}")


def choose_layout(requested: str, src: Path) -> str:
    if requested in ("crop", "fit_blur", "split"):
        return requested
    w, h = video_size(src)
    return "crop" if h >= w else "fit_blur"  # vertical já preenche; horizontal: não corta ninguém


def render(src: Path, segments: list[dict], words: list[dict], out_dir: Path, *, hook_text: str,
           layout: str, opts: dict, subtitle_style: dict | None = None, edits: list[dict] | None = None) -> dict:
    from .effects import EffectContext, build_filters

    layout = choose_layout(layout, src)
    vf, caption_mv = layout_filter(layout, opts, video_size(src))
    parts, sub_words, t = [], [], 0.0
    for i, sg in enumerate(segments):
        dur = sg["end"] - sg["start"]
        part = out_dir / f"part_{i:02d}.mp4"
        fade_out = max(dur - 0.06, 0)
        run(["ffmpeg", "-y", "-ss", f"{sg['start']:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
             "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0",
             "-af", f"afade=t=in:d=0.03,afade=t=out:st={fade_out:.3f}:d=0.06,aresample=48000",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-c:a", "aac", "-b:a", "256k",
             "-ac", "2", str(part)])
        real = float(probe(part)["format"]["duration"])
        for w in words:
            if sg["start"] <= w["s"] < sg["end"] and any(c.isalnum() for c in w["w"]):
                sub_words.append(Word(w["w"], t + w["s"] - sg["start"], t + min(w["e"], sg["end"]) - sg["start"]))
        parts.append(part)
        t += real

    lst = out_dir / "parts.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", "joined.mp4"], cwd=out_dir)

    subs = out_dir / "subs.ass"
    n_events = build_ass(sub_words, subs, hook_text=hook_text, total_duration=t, caption_margin_v=caption_mv,
                         style=subtitle_style)
    # efeitos de edição (registro em render/effects) entram antes das legendas
    fx_v, fx_a, fx_warn = build_filters(edits or [], segments, EffectContext(W, H, FPS, layout, t))
    vchain = ",".join([*fx_v, f"ass={subs.name}", "scale=out_range=tv", "format=yuv420p"])
    achain = ",".join([*fx_a, "loudnorm=I=-14:TP=-1.5:LRA=11"])
    run([
        "ffmpeg", "-y", "-i", "joined.mp4",
        "-vf", vchain, "-color_range", "tv",
        "-af", achain,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "10M", "-bufsize", "20M",
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 2),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "final.mp4",
    ], cwd=out_dir)
    for p in parts:
        p.unlink(missing_ok=True)
    (out_dir / "joined.mp4").unlink(missing_ok=True)
    final = out_dir / "final.mp4"
    duration = float(probe(final)["format"]["duration"])
    preview = discord_preview(final, out_dir / "preview.mp4", duration)
    return {"path": final, "preview": preview, "layout": layout, "subtitle_events": n_events,
            "duration": duration, "effect_warnings": fx_warn}


def discord_preview(final: Path, out: Path, duration: float, max_mb: float = 9.0) -> Path:
    """Versão leve (720x1280) que cabe no limite de upload do Discord sem boost (10 MB)."""
    budget_kbps = int(max_mb * 8 * 1024 / max(duration, 1)) - 96
    for kbps in (max(250, budget_kbps), max(200, int(budget_kbps * 0.75))):
        run(["ffmpeg", "-y", "-i", str(final), "-vf", "scale=720:1280", "-c:v", "libx264", "-preset", "medium",
             "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.3)}k", "-bufsize", f"{kbps * 2}k",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)])
        if out.stat().st_size <= max_mb * 1024 * 1024:
            break
    return out


def qc(path: Path, subtitle_events: int) -> dict:
    checks = []

    def add(name, ok, detail=None, severity="error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "severity": severity})

    info = probe(path)
    vs = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    aus = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    add("duration", 5 <= dur <= 180, round(dur, 2))
    add("video_stream", vs is not None)
    add("audio_stream", aus is not None)
    if vs:
        add("resolution_1080x1920", (vs["width"], vs["height"]) == (W, H), f"{vs['width']}x{vs['height']}")
        add("codec_h264", vs["codec_name"] == "h264", vs["codec_name"])
        add("pix_fmt_yuv420p", vs.get("pix_fmt") == "yuv420p", vs.get("pix_fmt"))
    if aus:
        add("codec_aac", aus["codec_name"] == "aac", aus["codec_name"])
    add("subtitles_present", subtitle_events > 0, subtitle_events)
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", "blackdetect=d=0.5:pix_th=0.10",
                        "-af", "silencedetect=noise=-45dB:d=2", "-f", "null", "-"], capture_output=True, text=True)
    black = sum(float(x.split("black_duration:")[1].split()[0]) for x in p.stderr.splitlines() if "black_duration:" in x)
    silence = sum(float(x.split("silence_duration:")[1].split()[0])
                  for x in p.stderr.splitlines() if "silence_duration:" in x)
    add("no_black_screen", black < 1.0, round(black, 2))
    add("no_long_silence", silence < 3.0, round(silence, 2), severity="warning")
    return {"passed": all(c["ok"] for c in checks if c["severity"] == "error"), "checks": checks}
