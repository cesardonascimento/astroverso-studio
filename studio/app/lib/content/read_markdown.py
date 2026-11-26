from pathlib import Path

import frontmatter

from app.lib.content.markdown_document import MarkdownDocument


class ReadMarkdown:
    def execute(self, path: Path) -> MarkdownDocument:
        post = frontmatter.load(path)
        return MarkdownDocument(path=path, meta=dict(post.metadata), body=post.content.strip())
