from pathlib import Path

from app.lib.webdav.connection import WebdavConnection


class UploadToWebdav:
    def __init__(self, connection: WebdavConnection):
        self.connection = connection

    def execute(self, source: Path | bytes, path: str, content_type: str) -> str:
        with self.connection.client() as client:
            if isinstance(source, bytes):
                response = client.put(self.connection.address(path), content=source,
                                      headers={"Content-Type": content_type})
            else:
                with source.open("rb") as file:
                    response = client.put(self.connection.address(path), content=file,
                                          headers={"Content-Type": content_type})
            response.raise_for_status()
        return path
