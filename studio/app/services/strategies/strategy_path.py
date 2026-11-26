import re
import unicodedata
from pathlib import Path

from app.config import CONTENT_DIR


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def strategy_path(network: str, name: str) -> Path:
    return CONTENT_DIR / "networks" / slugify(network) / "strategies" / f"{slugify(name)}.md"
