from pathlib import Path

from app.lib.ffmpeg.run_command import run_command


class ExtractAudio:
    def execute(self, source: Path, destination: Path) -> Path:
        run_command(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-ac", "1", "-ar", "16000", str(destination)])
        return destination
