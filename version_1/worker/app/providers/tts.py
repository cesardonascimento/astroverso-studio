"""Text-to-speech. Cada provider grava um .mp3 e devolve o tempo de cada palavra
(usado para legendas sincronizadas palavra por palavra)."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from ..db import record_generation


@dataclass
class Word:
    text: str
    start: float  # segundos
    end: float


@dataclass
class TTSResult:
    path: Path
    words: list[Word]
    provider: str
    voice: str


class TTSProvider:
    name = "base"

    def synthesize(self, text: str, out: Path, *, voice: str | None = None,
                   rate: str | None = None, ctx: dict | None = None) -> TTSResult:  # pragma: no cover
        raise NotImplementedError


class EdgeTTS(TTSProvider):
    """Vozes neurais da Microsoft pelo serviço do Edge (biblioteca edge-tts).
    Grátis e com ótima qualidade em pt-BR, mas NÃO é API oficial: ótimo para validar,
    trocar por Azure Speech (mesmas vozes, API oficial, 0,5M caracteres/mês grátis) depois."""

    name = "edge"

    def synthesize(self, text, out, *, voice=None, rate=None, ctx=None):
        import edge_tts

        voice = voice or settings().tts_voice
        rate = rate or settings().tts_rate
        words: list[Word] = []

        async def run() -> None:
            comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
            with open(out, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / 1e7  # unidades de 100ns
                        words.append(Word(chunk["text"], start, start + chunk["duration"] / 1e7))

        t0 = time.monotonic()
        try:
            asyncio.run(run())
        except Exception as e:
            record_generation(step="tts", provider=self.name, model=voice, units=len(text), cost_usd=0,
                              duration_ms=int((time.monotonic() - t0) * 1000), ok=False, error=repr(e)[:2000],
                              **(ctx or {}))
            raise
        record_generation(step="tts", provider=self.name, model=voice, units=len(text), cost_usd=0,
                          duration_ms=int((time.monotonic() - t0) * 1000), ok=True, **(ctx or {}))
        return TTSResult(out, words, self.name, voice)


def tts_provider() -> TTSProvider:
    return {"edge": EdgeTTS}[settings().tts_provider]()
