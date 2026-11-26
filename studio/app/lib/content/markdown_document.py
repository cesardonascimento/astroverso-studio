from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MarkdownDocument:
    path: Path
    meta: dict = field(default_factory=dict)
    body: str = ""
