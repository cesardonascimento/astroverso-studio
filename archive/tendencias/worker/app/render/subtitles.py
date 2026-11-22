"""Legendas .ass estilo TikTok: grupos de até 3 palavras, palavra atual destacada.

Área segura (inferência a partir da interface do TikTok, não é spec oficial):
  - embaixo ~30% da tela fica coberto por legenda do post / nome / música
  - lateral direita ~150px coberta pelos botões (curtir, comentar...)
  - topo ~200px coberto pelas abas
Por isso as legendas ficam por volta de 60-68% da altura e o gancho a ~17% do topo.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..providers.tts import Word

HIGHLIGHT = "&H0000E5FF&"  # amarelo (formato ASS: &HBBGGRR)
WHITE = "&H00FFFFFF&"

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Montserrat,88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,110,170,640,1
Style: Hook,Montserrat,82,&H00FFFFFF,&H00FFFFFF,&HB0000000,&H00000000,-1,0,0,0,100,100,0,0,3,22,0,8,110,170,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


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
        too_long = cur and (len(cur) >= max_words or sum(len(x.text) + 1 for x in cur) + len(w.text) > max_chars)
        if too_long:
            groups.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?,;:]$", w.text):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def build_ass(words: list[Word], out: Path, *, hook_text: str = "", hook_until: float = 2.5,
              total_duration: float | None = None) -> int:
    """Escreve o .ass e devolve o número de eventos de legenda."""
    lines = [HEADER]
    if hook_text:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(hook_until)},Hook,,0,0,0,,{_esc(hook_text.upper())}\n")

    groups = group_words(words)
    n = 0
    for gi, g in enumerate(groups):
        nxt = groups[gi + 1][0].start if gi + 1 < len(groups) else (total_duration or g[-1].end + 0.4)
        g_end = nxt if nxt - g[-1].end < 0.35 else g[-1].end + 0.15  # evita piscar entre grupos
        for wi, w in enumerate(g):
            start = w.start
            end = g[wi + 1].start if wi + 1 < len(g) else g_end
            parts = []
            for j, x in enumerate(g):
                txt = _esc(x.text.upper())
                parts.append(f"{{\\c{HIGHLIGHT}}}{txt}{{\\c{WHITE}}}" if j == wi else txt)
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Caption,,0,0,0,,{' '.join(parts)}\n")
            n += 1
    out.write_text("".join(lines), encoding="utf-8")
    return n
