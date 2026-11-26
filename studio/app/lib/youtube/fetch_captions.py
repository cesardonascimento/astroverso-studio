from dataclasses import dataclass

import httpx

from app.lib.media import Word
from app.lib.youtube.parse_json3 import ParseJson3
from app.lib.youtube.video_info import VideoInfo

MINIMUM_WORDS = 20


@dataclass
class Captions:
    source: str
    words: list[Word]


class FetchCaptions:
    def execute(self, video: VideoInfo) -> Captions | None:
        candidates = [("youtube_auto", self._pick(video.automatic_captions, video.language, automatic=True)),
                      ("youtube_manual", self._pick(video.subtitles, video.language, automatic=False))]
        for source, track in candidates:
            if not track:
                continue
            code, url = track
            words = self._download(url)
            if len(words) > MINIMUM_WORDS:
                return Captions(source=f"{source}:{code}", words=words)
        return None

    def _download(self, url: str) -> list[Word]:
        try:
            response = httpx.get(url, timeout=60)
            response.raise_for_status()
            return ParseJson3().execute(response.json())
        except (httpx.HTTPError, ValueError):
            return []

    def _pick(self, tracks: dict, language: str | None, automatic: bool) -> tuple[str, str] | None:
        base = (language or "pt").split("-")[0].lower()
        keys = list(tracks)
        if automatic:
            preferred = [key for key in keys if key.lower().endswith("-orig") and key.lower().startswith(base)]
            preferred += [key for key in keys if key.lower().endswith("-orig")]
            preferred += [key for key in keys if key.lower() in (base, f"{base}-br")]
        else:
            preferred = [key for key in keys if key.lower().split("-")[0] == base]
        for key in preferred:
            json3 = next((item for item in tracks[key] if item.get("ext") == "json3"), None)
            if json3:
                return key, json3["url"]
        return None
