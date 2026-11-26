from app.lib.webdav.connection import WebdavConnection


class EnsureFolder:
    def __init__(self, connection: WebdavConnection):
        self.connection = connection

    def execute(self, path: str) -> None:
        current = ""
        with self.connection.client() as client:
            for part in [part for part in path.strip("/").split("/") if part]:
                current = f"{current}/{part}"
                response = client.request("MKCOL", self.connection.address(current))
                if response.status_code not in (201, 405):
                    response.raise_for_status()
