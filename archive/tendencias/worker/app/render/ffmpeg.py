"""Wrappers de FFmpeg. Parâmetros de saída (H.264 + AAC, 1080x1920, 30 fps, MP4 faststart)
seguem os formatos aceitos pelo TikTok (MP4/H.264) — conferir na doc do Content Posting API."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

FPS = 30
W, H = 1080, 1920


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise FFmpegError(f"{args[0]} falhou ({p.returncode}): {p.stderr[-3000:]}")
    return p


def probe(path: Path) -> dict:
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(p.stdout)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def frames_for(seconds: float) -> int:
    return max(1, math.ceil(seconds * FPS))


def scene_clip(image: Path, seconds: float, out: Path, *, zoom_in: bool = True) -> float:
    """Imagem parada → clipe com zoom lento (Ken Burns). Devolve a duração exata do clipe."""
    n = frames_for(seconds)
    step = 0.10 / n  # 10% de zoom ao longo da cena
    z = f"1+{step:.6f}*on" if zoom_in else f"1.10-{step:.6f}*on"
    vf = (
        f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase:out_range=tv,crop={W * 2}:{H * 2},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
        "format=yuv420p"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(image), "-vf", vf,
         "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-an", str(out)])
    return n / FPS


def concat_video(clips: list[Path], out: Path) -> None:
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", out.name], cwd=out.parent)


def concat_audio(parts: list[tuple[Path, float]], out: Path) -> None:
    """Concatena as narrações, cada uma ajustada (pad/trim) à duração do seu clipe."""
    args = ["ffmpeg", "-y"]
    for p, _ in parts:
        args += ["-i", str(p)]
    chains = "".join(
        f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{d:.4f}[a{i}];"
        for i, (_, d) in enumerate(parts)
    )
    inputs = "".join(f"[a{i}]" for i in range(len(parts)))
    args += ["-filter_complex", f"{chains}{inputs}concat=n={len(parts)}:v=0:a=1[out]", "-map", "[out]",
             "-c:a", "pcm_s16le", str(out)]
    run(args)


def final_encode(video: Path, audio: Path, subs: Path, out: Path) -> None:
    """Passo final: legendas queimadas + loudness normalizado + encode de entrega.

    - H.264 High, yuv420p, 30 fps, GOP 2 s, CRF 20 com teto de 10 Mbps
    - AAC 192 kbps 48 kHz estéreo
    - loudnorm -14 LUFS / -1.5 dBTP (prática comum em plataformas; o TikTok não publica um alvo oficial)
    - +faststart (moov no início)
    """
    run([
        "ffmpeg", "-y", "-i", video.name, "-i", audio.name,
        # JPEG entra como full range (yuvj420p): força limited range + yuv420p para compatibilidade
        "-vf", f"ass={subs.name},scale=out_range=tv,format=yuv420p", "-color_range", "tv",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "10M", "-bufsize", "20M",
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 2),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-shortest", out.name,
    ], cwd=out.parent)


def scan_content(path: Path) -> dict:
    """Uma passada decodificando tudo: telas pretas, silêncios longos e erros de decodificação."""
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-vf", "blackdetect=d=0.5:pix_th=0.10", "-af", "silencedetect=noise=-45dB:d=1.5",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    err = p.stderr
    black = [float(x.split("black_duration:")[1].split()[0]) for x in err.splitlines() if "black_duration:" in x]
    silence = [float(x.split("silence_duration:")[1].split()[0]) for x in err.splitlines() if "silence_duration:" in x]
    decode_errors = [x for x in err.splitlines() if "error while decoding" in x.lower() or "corrupt" in x.lower()]
    return {
        "returncode": p.returncode,
        "black_segments": len(black), "black_total_s": round(sum(black), 2),
        "silence_segments": len(silence), "silence_total_s": round(sum(silence), 2),
        "decode_errors": decode_errors[:10],
    }
