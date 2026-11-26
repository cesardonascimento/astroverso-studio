from pathlib import Path

from botocore.client import BaseClient


class DownloadFile:
    def __init__(self, client: BaseClient, bucket: str):
        self.client = client
        self.bucket = bucket

    def execute(self, key: str, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(path))
        return path
