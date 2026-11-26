from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VideoInfo:
    id: str
    title: str
    channel: str
    duration_s: float
    language: str | None
    path: Path
    automatic_captions: dict = field(default_factory=dict)
    subtitles: dict = field(default_factory=dict)
