import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def run_command(args: list[str], cwd: Path | None = None) -> str:
    process = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if process.returncode != 0:
        raise FFmpegError(f"{args[0]} falhou ({process.returncode}): {process.stderr[-3000:]}")
    return process.stderr
