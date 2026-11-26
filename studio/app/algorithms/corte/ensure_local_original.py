from pathlib import Path

from app.algorithms.base import StepFailed
from app.algorithms.corte.files import generation_dir
from app.dependencies import download_file
from app.models import Generation


class EnsureLocalOriginal:
    def execute(self, generation: Generation, workspace: Path) -> Path:
        local = generation_dir(workspace, generation.id) / "original.mp4"
        if local.exists():
            return local
        if not generation.original_key:
            raise StepFailed("o vídeo original foi apagado; crie uma nova geração")
        return download_file().execute(generation.original_key, local)
