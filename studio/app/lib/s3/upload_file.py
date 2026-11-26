from pathlib import Path

from botocore.client import BaseClient


class UploadFile:
    def __init__(self, client: BaseClient, bucket: str):
        self.client = client
        self.bucket = bucket

    def execute(self, path: Path, key: str, content_type: str = "application/octet-stream") -> str:
        self.client.upload_file(str(path), self.bucket, key, ExtraArgs={"ContentType": content_type})
        return key
