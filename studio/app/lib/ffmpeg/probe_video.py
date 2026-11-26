import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoProbe:
    width: int
    height: int
    duration: float
    video_codec: str | None
    pixel_format: str | None
    audio_codec: str | None


class ProbeVideo:
    def execute(self, path: Path) -> VideoProbe:
        output = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                                 str(path)], capture_output=True, text=True, check=True).stdout
        data = json.loads(output)
        video = next((stream for stream in data["streams"] if stream["codec_type"] == "video"), {})
        audio = next((stream for stream in data["streams"] if stream["codec_type"] == "audio"), {})
        return VideoProbe(width=int(video.get("width", 0)), height=int(video.get("height", 0)),
                          duration=float(data["format"].get("duration", 0)), video_codec=video.get("codec_name"),
                          pixel_format=video.get("pix_fmt"), audio_codec=audio.get("codec_name"))
