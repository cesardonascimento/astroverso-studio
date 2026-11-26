from dataclasses import dataclass, field

from app.lib.ffmpeg import SubtitleStyle


@dataclass
class Strategy:
    network: str
    name: str
    description: str
    text: str


@dataclass
class Network:
    id: str
    name: str
    min_duration_s: int
    max_duration_s: int
    hashtags: str
    caption: str
    subtitle_preset: str
    layout: str
    guidance: str
    strategies: list[Strategy] = field(default_factory=list)


@dataclass
class SubtitlePreset:
    name: str
    description: str
    style: SubtitleStyle


AUTO_STRATEGY = "auto"
