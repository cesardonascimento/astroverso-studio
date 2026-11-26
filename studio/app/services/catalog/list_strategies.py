from app.config import CONTENT_DIR
from app.lib.content import ListMarkdown
from app.services.catalog.entries import Strategy


class ListStrategies:
    def execute(self, network: str) -> list[Strategy]:
        documents = ListMarkdown().execute(CONTENT_DIR / "networks" / network / "strategies")
        return [Strategy(network=network, name=str(document.meta.get("name", document.path.stem)),
                         description=str(document.meta.get("description", "")), text=document.body)
                for document in documents]
