from dataclasses import fields

from app.config import CONTENT_DIR
from app.lib.content import ListMarkdown
from app.lib.ffmpeg import SubtitleStyle
from app.services.catalog.entries import SubtitlePreset

STYLE_KEYS = {item.name for item in fields(SubtitleStyle)}


class ListSubtitlePresets:
    def execute(self) -> list[SubtitlePreset]:
        return [SubtitlePreset(name=str(document.meta.get("name", document.path.stem)),
                               description=str(document.meta.get("description", "")),
                               style=SubtitleStyle(**{key: value for key, value in document.meta.items()
                                                      if key in STYLE_KEYS}))
                for document in ListMarkdown().execute(CONTENT_DIR / "subtitles")]
