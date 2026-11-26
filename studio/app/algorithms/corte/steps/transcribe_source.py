import json

from app.algorithms.base import Step, StepContext, StepFailed
from app.algorithms.corte.ensure_local_original import EnsureLocalOriginal
from app.algorithms.corte.files import generation_dir, transcript_key
from app.config import settings
from app.dependencies import transcribe_audio, upload_file
from app.lib.ffmpeg import ExtractAudio
from app.lib.media import Word
from app.lib.youtube import FetchCaptions, VideoInfo

MINIMUM_WORDS = 20


class TranscribeSource(Step):
    name = "transcribe"
    label = "Transcrição"

    def execute(self, context: StepContext) -> str:
        generation = context.generation
        directory = generation_dir(context.workspace, generation.id)
        source, words = self._from_captions(generation.source, directory) or self._from_whisper(context, directory)
        if len(words) < MINIMUM_WORDS:
            raise StepFailed("a transcrição saiu vazia ou curta demais")
        transcript = directory / "transcript.json"
        transcript.write_text(json.dumps([word.to_dict() for word in words], ensure_ascii=False), encoding="utf-8")
        upload_file().execute(transcript, transcript_key(generation.id), "application/json")
        generation.source = {**generation.source, "transcript_source": source, "transcript_words": len(words)}
        return f"{len(words)} palavras ({source})"

    def _from_captions(self, source: dict, directory) -> tuple[str, list[Word]] | None:
        captions_file = directory / "captions.json"
        if not captions_file.exists():
            return None
        captions = json.loads(captions_file.read_text(encoding="utf-8"))
        video = VideoInfo(id=source.get("id", ""), title="", channel="", duration_s=0,
                          language=source.get("language"), path=directory,
                          automatic_captions=captions["automatic"], subtitles=captions["manual"])
        found = FetchCaptions().execute(video)
        return (found.source, found.words) if found else None

    def _from_whisper(self, context: StepContext, directory) -> tuple[str, list[Word]]:
        original = EnsureLocalOriginal().execute(context.generation, context.workspace)
        audio = ExtractAudio().execute(original, directory / "audio16k.wav")
        words = transcribe_audio().execute(audio, context.generation.source.get("language"))
        audio.unlink(missing_ok=True)
        return f"whisper:{settings().whisper_model}", words
