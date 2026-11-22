"""Legendas .ass estilo TikTok, com estilo vindo de config/presets.json.

Área segura (inferência pela interface do TikTok, não é spec oficial): rodapé ~30% e lateral direita
~150px ficam cobertos pela interface; topo ~200px pelas abas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float


DEFAULT_STYLE = {
    "font": "Montserrat", "size": 88, "bold": True, "uppercase": True,
    "color": "#FFFFFF", "highlight": "#FFE500", "outline_color": "#000000",
    "outline": 7, "shadow": 3, "max_words": 3, "max_chars": 18,
}


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR (formato do ASS)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def group_words(words: list[Word], max_words: int = 3, max_chars: int = 18) -> list[list[Word]]:
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur and (len(cur) >= max_words or sum(len(x.text) + 1 for x in cur) + len(w.text) > max_chars):
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?,;:]$", w.text):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def header(style: dict, caption_margin_v: int) -> str:
    st = {**DEFAULT_STYLE, **style}
    bold = -1 if st["bold"] else 0
    prim, outl = ass_color(st["color"]), ass_color(st["outline_color"])
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{st['font']},{st['size']},{prim},{prim},{outl},&H80000000,{bold},0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},2,110,170,{caption_margin_v},1
Style: Hook,{st['font']},82,&H00FFFFFF,&H00FFFFFF,&HB0000000,&H00000000,-1,0,0,0,100,100,0,0,3,22,0,8,110,170,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(words: list[Word], out: Path, *, hook_text: str = "", hook_until: float = 2.5,
              total_duration: float | None = None, caption_margin_v: int = 640,
              style: dict | None = None) -> int:
    """Escreve o .ass e devolve o número de eventos de legenda."""
    st = {**DEFAULT_STYLE, **(style or {})}
    hi, base = ass_color(st["highlight"]) + "&", ass_color(st["color"]) + "&"
    up = (lambda s: s.upper()) if st["uppercase"] else (lambda s: s)  # noqa: E731
    lines = [header(st, caption_margin_v)]
    if hook_text:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(hook_until)},Hook,,0,0,0,,{_esc(hook_text.upper())}\n")

    groups = group_words(words, st["max_words"], st["max_chars"])
    n = 0
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0].start if gi + 1 < len(groups) else (total_duration or g[-1].end + 0.4)
        g_end = nxt if nxt - g[-1].end < 0.35 else g[-1].end + 0.15
        same_color = st["highlight"].lower() == st["color"].lower()
        if same_color:  # sem destaque: um evento por grupo
            lines.append(f"Dialogue: 0,{_ts(g[0].start)},{_ts(g_end)},Caption,,0,0,0,,"
                         f"{' '.join(_esc(up(x.text)) for x in g)}\n")
            n += 1
            continue
        for wi, w in enumerate(g):
            end = g[wi + 1].start if wi + 1 < len(g) else g_end
            parts = [f"{{\\c{hi}}}{_esc(up(x.text))}{{\\c{base}}}" if j == wi else _esc(up(x.text))
                     for j, x in enumerate(g)]
            lines.append(f"Dialogue: 0,{_ts(w.start)},{_ts(end)},Caption,,0,0,0,,{' '.join(parts)}\n")
            n += 1
    out.write_text("".join(lines), encoding="utf-8")
    return n
