from pathlib import Path

from app.lib.content.markdown_document import MarkdownDocument
from app.lib.content.read_markdown import ReadMarkdown


class ListMarkdown:
    def execute(self, directory: Path) -> list[MarkdownDocument]:
        if not directory.is_dir():
            return []
        return [ReadMarkdown().execute(path) for path in sorted(directory.glob("*.md"))]
