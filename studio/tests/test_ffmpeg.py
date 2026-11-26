import subprocess
from pathlib import Path

from app.lib.ffmpeg import BuildFrameLayout, CheckVideoQuality, ProbeVideo, RenderVerticalCut, SubtitleStyle
from app.lib.ffmpeg.write_subtitles import WriteSubtitles
from app.lib.media import Segment, Word


def make_source(path: Path, size: str = "1280x720", seconds: int = 20) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds), "-c:v", "libx264",
                    "-c:a", "aac", str(path)], check=True)
    return path


def test_auto_layout_follows_orientation():
    assert BuildFrameLayout().execute("auto", {}, (1920, 1080)).name == "fit_blur"
    assert BuildFrameLayout().execute("auto", {}, (1080, 1920)).name == "crop"


def test_subtitles_highlight_each_word(tmp_path):
    words = [Word("um", 0.0, 0.4), Word("dois", 0.4, 0.8), Word("tres.", 0.8, 1.2), Word("quatro", 1.3, 1.6)]
    events = WriteSubtitles(SubtitleStyle()).execute(words, tmp_path / "s.ass", "gancho", 2.0, 640)
    content = (tmp_path / "s.ass").read_text()
    assert events == 4
    assert "GANCHO" in content and "{\\c&H0000E5FF&}DOIS" in content


def test_render_produces_vertical_video_that_passes_quality(tmp_path):
    source = make_source(tmp_path / "source.mp4")
    words = [Word(f"palavra{i}", i * 0.5, i * 0.5 + 0.4) for i in range(40)]
    cut = RenderVerticalCut(SubtitleStyle()).execute(source, [Segment(1, 5), Segment(10, 14)], words,
                                                     tmp_path / "render", "gancho", "auto", {})
    probe = ProbeVideo().execute(cut.path)
    assert (probe.width, probe.height) == (1080, 1920)
    assert 7.5 < cut.duration < 8.5
    assert cut.layout == "fit_blur"
    report = CheckVideoQuality().execute(cut.path, cut.subtitle_events)
    assert report.passed, report.to_dict()
