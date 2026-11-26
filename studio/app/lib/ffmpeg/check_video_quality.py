import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.lib.ffmpeg.frame_layout import HEIGHT, WIDTH
from app.lib.ffmpeg.probe_video import ProbeVideo


@dataclass
class QualityCheck:
    name: str
    ok: bool
    detail: str
    blocking: bool = True


@dataclass
class QualityReport:
    checks: list[QualityCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.ok for check in self.checks if check.blocking)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": [vars(check) for check in self.checks]}


class CheckVideoQuality:
    def execute(self, path: Path, subtitle_events: int) -> QualityReport:
        probe = ProbeVideo().execute(path)
        black, silence = self._black_and_silence(path)
        return QualityReport([
            QualityCheck("duração entre 5 e 180 s", 5 <= probe.duration <= 180, f"{probe.duration:.1f} s"),
            QualityCheck(f"resolução {WIDTH}x{HEIGHT}", (probe.width, probe.height) == (WIDTH, HEIGHT),
                         f"{probe.width}x{probe.height}"),
            QualityCheck("vídeo H.264", probe.video_codec == "h264", str(probe.video_codec)),
            QualityCheck("pixel yuv420p", probe.pixel_format == "yuv420p", str(probe.pixel_format)),
            QualityCheck("áudio AAC", probe.audio_codec == "aac", str(probe.audio_codec)),
            QualityCheck("legendas presentes", subtitle_events > 0, str(subtitle_events)),
            QualityCheck("sem tela preta", black < 1.0, f"{black:.1f} s"),
            QualityCheck("sem silêncio longo", silence < 3.0, f"{silence:.1f} s", blocking=False),
        ])

    def _black_and_silence(self, path: Path) -> tuple[float, float]:
        stderr = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                                 "-vf", "blackdetect=d=0.5:pix_th=0.10", "-af", "silencedetect=noise=-45dB:d=2",
                                 "-f", "null", "-"], capture_output=True, text=True).stderr.splitlines()
        black = sum(float(line.split("black_duration:")[1].split()[0]) for line in stderr if "black_duration:" in line)
        silence = sum(float(line.split("silence_duration:")[1].split()[0])
                      for line in stderr if "silence_duration:" in line)
        return black, silence
