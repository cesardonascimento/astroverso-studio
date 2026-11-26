import pytest

from app.config import settings
from app.lib.s3 import DeleteObject, DownloadFile, EnsureBucket, ReadObject, UploadFile, s3_client


@pytest.fixture
def bucket():
    config = settings()
    client = s3_client(config.s3_endpoint, config.s3_access_key, config.s3_secret_key)
    name = f"{config.s3_bucket}-test"
    EnsureBucket(client).execute(name)
    return client, name


def test_upload_read_range_download_and_delete(bucket, tmp_path):
    client, name = bucket
    source = tmp_path / "a.txt"
    source.write_bytes(b"0123456789")
    UploadFile(client, name).execute(source, "x/a.txt", "text/plain")

    stream = ReadObject(client, name).execute("x/a.txt", "bytes=2-4")
    assert b"".join(stream.chunks) == b"234"
    assert stream.total_size == 10 and stream.content_range == "bytes 2-4/10"

    copy = DownloadFile(client, name).execute("x/a.txt", tmp_path / "b" / "a.txt")
    assert copy.read_bytes() == b"0123456789"

    DeleteObject(client, name).execute("x/a.txt")
    with pytest.raises(Exception):
        ReadObject(client, name).execute("x/a.txt")
