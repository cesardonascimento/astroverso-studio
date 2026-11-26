import markdown


class RenderMarkdown:
    def execute(self, text: str) -> str:
        escaped = text.replace("&", "&amp;").replace("<", "&lt;")
        return markdown.markdown(escaped, extensions=["sane_lists"])
