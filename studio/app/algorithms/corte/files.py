from pathlib import Path


def generation_dir(workspace: Path, generation_id: int) -> Path:
    path = workspace / "generations" / str(generation_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_dir(workspace: Path, output_id: int, version: int) -> Path:
    path = workspace / "outputs" / str(output_id) / f"v{version}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def original_key(generation_id: int) -> str:
    return f"generations/{generation_id}/original.mp4"


def transcript_key(generation_id: int) -> str:
    return f"generations/{generation_id}/transcript.json"


def video_key(output_id: int, version: int) -> str:
    return f"outputs/{output_id}/v{version}/final.mp4"

