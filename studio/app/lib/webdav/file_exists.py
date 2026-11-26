from app.lib.webdav.connection import WebdavConnection


class FileExists:
    def __init__(self, connection: WebdavConnection):
        self.connection = connection

    def execute(self, path: str) -> bool:
        with self.connection.client() as client:
            return client.head(self.connection.address(path)).status_code == 200
