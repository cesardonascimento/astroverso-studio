from botocore.client import BaseClient


class DeleteObject:
    def __init__(self, client: BaseClient, bucket: str):
        self.client = client
        self.bucket = bucket

    def execute(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
