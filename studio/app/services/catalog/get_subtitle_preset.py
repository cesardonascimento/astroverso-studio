from app.lib.ffmpeg import SubtitleStyle
from app.services.catalog.entries import SubtitlePreset
from app.services.catalog.list_subtitle_presets import ListSubtitlePresets


class GetSubtitlePreset:
    def execute(self, name: str | None) -> SubtitlePreset:
        presets = ListSubtitlePresets().execute()
        chosen = next((preset for preset in presets if preset.name == name), None)
        if chosen:
            return chosen
        if presets:
            return presets[0]
        return SubtitlePreset(name="padrao", description="", style=SubtitleStyle())
