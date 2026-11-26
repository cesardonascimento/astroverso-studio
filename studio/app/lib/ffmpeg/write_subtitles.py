import re
from dataclasses import dataclass
from pathlib import Path

from app.lib.media import Word


@dataclass(frozen=True)
class SubtitleStyle:
    font: str = "Montserrat"
    size: int = 88
    bold: bool = True
    uppercase: bool = True
    color: str = "#FFFFFF"
    highlight: str = "#FFE500"
    outline_color: str = "#000000"
    outline: int = 7
    shadow: int = 3
    max_words: int = 3
    max_chars: int = 18


class WriteSubtitles:
    def __init__(self, style: SubtitleStyle):
        self.style = style

    def execute(self, words: list[Word], destination: Path, hook_text: str, total_duration: float,
                caption_margin: int) -> int:
        lines = [self._header(caption_margin)]
        if hook_text:
            lines.append(f"Dialogue: 1,{self._time(0)},{self._time(2.5)},Hook,,0,0,0,,{self._escape(hook_text.upper())}")
        groups = self._group(words)
        events = 0
        for index, group in enumerate(groups):
            following = groups[index + 1][0].start if index + 1 < len(groups) else total_duration
            group_end = following if following - group[-1].end < 0.35 else group[-1].end + 0.15
            new_lines = self._group_events(group, group_end)
            lines.extend(new_lines)
            events += len(new_lines)
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return events

    def _group_events(self, group: list[Word], group_end: float) -> list[str]:
        if self.style.highlight.lower() == self.style.color.lower():
            text = " ".join(self._escape(self._case(word.text)) for word in group)
            return [f"Dialogue: 0,{self._time(group[0].start)},{self._time(group_end)},Caption,,0,0,0,,{text}"]
        highlight, base = self._color(self.style.highlight) + "&", self._color(self.style.color) + "&"
        events = []
        for index, word in enumerate(group):
            end = group[index + 1].start if index + 1 < len(group) else group_end
            parts = [f"{{\\c{highlight}}}{self._escape(self._case(other.text))}{{\\c{base}}}" if position == index
                     else self._escape(self._case(other.text)) for position, other in enumerate(group)]
            events.append(f"Dialogue: 0,{self._time(word.start)},{self._time(end)},Caption,,0,0,0,,{' '.join(parts)}")
        return events

    def _group(self, words: list[Word]) -> list[list[Word]]:
        groups: list[list[Word]] = []
        current: list[Word] = []
        for word in words:
            current_chars = sum(len(item.text) + 1 for item in current)
            if current and (len(current) >= self.style.max_words or
                            current_chars + len(word.text) > self.style.max_chars):
                groups.append(current)
                current = []
            current.append(word)
            if re.search(r"[.!?,;:]$", word.text):
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        return groups

    def _header(self, caption_margin: int) -> str:
        style = self.style
        bold = -1 if style.bold else 0
        primary, outline = self._color(style.color), self._color(style.outline_color)
        return "\n".join([
            "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0",
            "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding",
            f"Style: Caption,{style.font},{style.size},{primary},{primary},{outline},&H80000000,{bold},0,0,0,100,100,"
            f"0,0,1,{style.outline},{style.shadow},2,110,170,{caption_margin},1",
            f"Style: Hook,{style.font},82,&H00FFFFFF,&H00FFFFFF,&HB0000000,&H00000000,-1,0,0,0,100,100,0,0,3,22,0,8,"
            "110,170,330,1",
            "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"])

    def _case(self, text: str) -> str:
        return text.upper() if self.style.uppercase else text

    def _color(self, hex_rgb: str) -> str:
        value = hex_rgb.lstrip("#")
        return f"&H00{value[4:6]}{value[2:4]}{value[0:2]}".upper()

    def _time(self, seconds: float) -> str:
        hours, rest = divmod(max(seconds, 0), 3600)
        minutes, secs = divmod(rest, 60)
        return f"{int(hours)}:{int(minutes):02d}:{secs:05.2f}"

    def _escape(self, text: str) -> str:
        return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")
