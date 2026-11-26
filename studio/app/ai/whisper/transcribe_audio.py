import logging
from functools import lru_cache
from pathlib import Path

from app.ai.whisper.resolve_device import ResolveWhisperDevice
from app.lib.media import Word

log = logging.getLogger(__name__)


@lru_cache
def _load_model(model: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model, device=device, compute_type=compute_type)


class TranscribeAudio:
    def __init__(self, model: str, device: str = "auto", compute_type: str = "auto"):
        self.model = model
        self.device = device
        self.compute_type = compute_type

    def execute(self, audio: Path, language: str | None) -> list[Word]:
        device = ResolveWhisperDevice().execute(self.device)
        try:
            return self._transcribe(audio, language, device)
        except RuntimeError as error:
            if device != "cuda":
                raise
            log.warning("whisper na GPU falhou (%s); usando a CPU", error)
            return self._transcribe(audio, language, "cpu")

    def _transcribe(self, audio: Path, language: str | None, device: str) -> list[Word]:
        compute_type = self.compute_type if self.compute_type != "auto" else (
            "int8_float16" if device == "cuda" else "int8")
        segments, _ = _load_model(self.model, device, compute_type).transcribe(
            str(audio), language=language.split("-")[0] if language else None, word_timestamps=True,
            vad_filter=True)
        return [Word(word.word.strip(), round(word.start, 3), round(word.end, 3))
                for segment in segments for word in (segment.words or []) if word.word.strip()]
