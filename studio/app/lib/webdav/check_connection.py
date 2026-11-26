import httpx

from app.lib.webdav.connection import WebdavConnection


class CheckWebdavConnection:
    def __init__(self, connection: WebdavConnection):
        self.connection = connection

    def execute(self) -> str:
        try:
            with self.connection.client() as client:
                response = client.request("PROPFIND", self.connection.address(""), headers={"Depth": "0"})
        except httpx.HTTPError as error:
            return f"sem conexão: {error}"
        if response.status_code == 401:
            return "usuário ou senha recusados"
        if response.status_code not in (200, 207):
            return f"o servidor respondeu {response.status_code}"
        return ""
