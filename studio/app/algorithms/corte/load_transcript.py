import json
from pathlib import Path

from app.algorithms.corte.files import generation_dir, transcript_key
from app.dependencies import download_file
from app.lib.media import Word
from app.models import Generation


class LoadTranscript:
    def execute(self, generation: Generation, workspace: Path) -> list[Word]:
        local = generation_dir(workspace, generation.id) / "transcript.json"
        if not local.exists():
            download_file().execute(transcript_key(generation.id), local)
        return [Word.from_dict(item) for item in json.loads(local.read_text(encoding="utf-8"))]
