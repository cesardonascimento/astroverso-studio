from app.config import CONTENT_DIR
from app.lib.content import ReadMarkdown
from app.services.catalog.entries import Network
from app.services.catalog.list_strategies import ListStrategies


class ListNetworks:
    def execute(self) -> list[Network]:
        directory = CONTENT_DIR / "networks"
        return [self._load(path.parent.name, path) for path in sorted(directory.glob("*/network.md"))]

    def _load(self, network_id: str, path) -> Network:
        document = ReadMarkdown().execute(path)
        meta = document.meta
        return Network(id=network_id, name=str(meta.get("name", network_id)),
                       min_duration_s=int(meta.get("min_duration_s", 15)),
                       max_duration_s=int(meta.get("max_duration_s", 60)), hashtags=str(meta.get("hashtags", "")),
                       caption=str(meta.get("caption", "")), subtitle_preset=str(meta.get("subtitle_preset", "")),
                       layout=str(meta.get("layout", "auto")), guidance=document.body,
                       strategies=ListStrategies().execute(network_id))
