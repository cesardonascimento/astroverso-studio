from collections.abc import Iterator
from dataclasses import dataclass

from botocore.client import BaseClient


@dataclass
class ObjectStream:
    chunks: Iterator[bytes]
    content_type: str
    content_length: int
    content_range: str | None
    total_size: int


class ReadObject:
    def __init__(self, client: BaseClient, bucket: str):
        self.client = client
        self.bucket = bucket

    def execute(self, key: str, byte_range: str | None = None) -> ObjectStream:
        request = {"Bucket": self.bucket, "Key": key}
        if byte_range:
            request["Range"] = byte_range
        response = self.client.get_object(**request)
        content_range = response.get("ContentRange")
        total = int(content_range.rsplit("/", 1)[1]) if content_range else int(response["ContentLength"])
        return ObjectStream(chunks=response["Body"].iter_chunks(1024 * 256),
                            content_type=response.get("ContentType", "application/octet-stream"),
                            content_length=int(response["ContentLength"]), content_range=content_range,
                            total_size=total)
