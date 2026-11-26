from botocore.client import BaseClient
from botocore.exceptions import ClientError


class EnsureBucket:
    def __init__(self, client: BaseClient):
        self.client = client

    def execute(self, bucket: str) -> None:
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError:
            self.client.create_bucket(Bucket=bucket)
