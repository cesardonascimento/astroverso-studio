import frontmatter

from app.lib.content.markdown_document import MarkdownDocument


class WriteMarkdown:
    def execute(self, document: MarkdownDocument) -> None:
        document.path.parent.mkdir(parents=True, exist_ok=True)
        post = frontmatter.Post(document.body.strip() + "\n", **document.meta)
        document.path.write_text(frontmatter.dumps(post, sort_keys=False) + "\n", encoding="utf-8")
