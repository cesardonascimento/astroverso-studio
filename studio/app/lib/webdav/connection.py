from dataclasses import dataclass
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class WebdavConnection:
    url: str
    user: str
    password: str

    def address(self, path: str) -> str:
        parts = [quote(part) for part in path.strip("/").split("/") if part]
        return self.url.rstrip("/") + "/" + "/".join(parts)

    def client(self) -> httpx.Client:
        return httpx.Client(auth=(self.user, self.password), timeout=httpx.Timeout(30, write=600))
