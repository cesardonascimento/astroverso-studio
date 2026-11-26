from dataclasses import dataclass
from pathlib import Path

from app.lib.ffmpeg.frame_layout import FPS, BuildFrameLayout
from app.lib.ffmpeg.probe_video import ProbeVideo
from app.lib.ffmpeg.run_command import run_command
from app.lib.ffmpeg.write_subtitles import SubtitleStyle, WriteSubtitles
from app.lib.media import Segment, Word


@dataclass
class RenderedCut:
    path: Path
    duration: float
    layout: str
    subtitle_events: int


class RenderVerticalCut:
    def __init__(self, style: SubtitleStyle):
        self.style = style

    def execute(self, source: Path, segments: list[Segment], words: list[Word], directory: Path, hook_text: str,
                layout: str, layout_options: dict) -> RenderedCut:
        directory.mkdir(parents=True, exist_ok=True)
        probe = ProbeVideo().execute(source)
        frame = BuildFrameLayout().execute(layout, layout_options, (probe.width, probe.height))
        parts, cut_words, cursor = [], [], 0.0
        for index, segment in enumerate(segments):
            part = directory / f"part_{index:02d}.mp4"
            self._render_part(source, segment, frame.video_filter, part)
            cut_words.extend(self._shift_words(words, segment, cursor))
            parts.append(part)
            cursor += ProbeVideo().execute(part).duration
        self._join(parts, directory)
        subtitles = directory / "subs.ass"
        events = WriteSubtitles(self.style).execute(cut_words, subtitles, hook_text, cursor, frame.caption_margin)
        self._finish(directory)
        for part in parts:
            part.unlink(missing_ok=True)
        (directory / "joined.mp4").unlink(missing_ok=True)
        final = directory / "final.mp4"
        return RenderedCut(path=final, duration=ProbeVideo().execute(final).duration, layout=frame.name,
                           subtitle_events=events)

    def _render_part(self, source: Path, segment: Segment, video_filter: str, part: Path) -> None:
        fade_out = max(segment.duration - 0.06, 0)
        run_command(["ffmpeg", "-y", "-ss", f"{segment.start:.3f}", "-i", str(source), "-t", f"{segment.duration:.3f}",
                     "-filter_complex", video_filter, "-map", "[v]", "-map", "0:a:0",
                     "-af", f"afade=t=in:d=0.03,afade=t=out:st={fade_out:.3f}:d=0.06,aresample=48000",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-c:a", "aac", "-b:a", "256k",
                     "-ac", "2", str(part)])

    def _shift_words(self, words: list[Word], segment: Segment, offset: float) -> list[Word]:
        return [Word(word.text, offset + word.start - segment.start, offset + min(word.end, segment.end) - segment.start)
                for word in words
                if segment.start <= word.start < segment.end and any(char.isalnum() for char in word.text)]

    def _join(self, parts: list[Path], directory: Path) -> None:
        listing = directory / "parts.txt"
        listing.write_text("".join(f"file '{part.name}'\n" for part in parts), encoding="utf-8")
        run_command(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing.name, "-c", "copy", "joined.mp4"],
                    cwd=directory)
        listing.unlink(missing_ok=True)

    def _finish(self, directory: Path) -> None:
        run_command(["ffmpeg", "-y", "-i", "joined.mp4", "-vf", "ass=subs.ass,scale=out_range=tv,format=yuv420p",
                     "-color_range", "tv", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                     "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "10M", "-bufsize", "20M",
                     "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 2),
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
                     "final.mp4"], cwd=directory)
