"""Registro de efeitos de edição (estrutura pronta, nenhum efeito implementado ainda).

Como funciona:
  - O plano do corte tem uma lista `edits`: [{"type": "zoom", "start": 412.3, "end": 415.0, "params": "{...}"}]
    com tempos no vídeo ORIGINAL (o mesmo relógio da transcrição que o LLM lê).
  - O renderizador converte esses tempos para a linha do tempo do corte e pede a cada efeito registrado
    o pedaço de filtro FFmpeg correspondente. Tipos desconhecidos são ignorados e anotados no QC.
  - O prompt do editor recebe `available()` — o LLM só pode propor efeitos que existem.

Para criar um efeito novo: um arquivo neste pacote com uma subclasse de Effect decorada com @register.

    @register
    class Zoom(Effect):
        name = "zoom"
        description = "zoom de ênfase num momento forte"
        params = {"scale": "1.0-1.3, padrão 1.15"}
        def video_filter(self, t0, t1, params, ctx):
            return f"zoompan=...:enable='between(t,{t0},{t1})'"
"""
from __future__ import annotations

import importlib
import json
import logging
import pkgutil
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class EffectContext:
    width: int
    height: int
    fps: int
    layout: str
    duration: float
    extra: dict = field(default_factory=dict)


class Effect:
    name: str = ""
    description: str = ""
    params: dict[str, str] = {}

    def video_filter(self, t0: float, t1: float, params: dict, ctx: EffectContext) -> str | None:
        """Filtro aplicado ao vídeo já montado (antes das legendas). t0/t1 na linha do tempo do corte."""
        return None

    def audio_filter(self, t0: float, t1: float, params: dict, ctx: EffectContext) -> str | None:
        return None


REGISTRY: dict[str, Effect] = {}


def register(cls: type[Effect]) -> type[Effect]:
    REGISTRY[cls.name] = cls()
    return cls


def _autoload() -> None:
    for m in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        importlib.import_module(f"{__name__}.{m.name}")


def available() -> list[dict]:
    return [{"type": e.name, "description": e.description, "params": e.params} for e in REGISTRY.values()]


def to_output_time(t: float, segments: list[dict]) -> float | None:
    """Tempo no vídeo original → tempo no corte (None se cair fora dos segmentos)."""
    acc = 0.0
    for sg in segments:
        if sg["start"] <= t <= sg["end"]:
            return acc + t - sg["start"]
        acc += sg["end"] - sg["start"]
    return None


def build_filters(edits: list[dict], segments: list[dict], ctx: EffectContext) -> tuple[list[str], list[str], list[str]]:
    """Devolve (filtros de vídeo, filtros de áudio, avisos)."""
    vf, af, warnings = [], [], []
    for e in edits or []:
        eff = REGISTRY.get(e.get("type", ""))
        if not eff:
            warnings.append(f"efeito desconhecido ignorado: {e.get('type')}")
            continue
        t0, t1 = to_output_time(e["start"], segments), to_output_time(e["end"], segments)
        if t0 is None or t1 is None or t1 <= t0:
            warnings.append(f"efeito {eff.name} fora dos segmentos: {e['start']}-{e['end']}")
            continue
        try:
            params = json.loads(e.get("params") or "{}")
        except json.JSONDecodeError:
            params = {}
        if (f := eff.video_filter(t0, t1, params, ctx)):
            vf.append(f)
        if (f := eff.audio_filter(t0, t1, params, ctx)):
            af.append(f)
    return vf, af, warnings


_autoload()
