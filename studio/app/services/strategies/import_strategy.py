import frontmatter

from app.services.catalog import Strategy
from app.services.strategies.save_strategy import InvalidStrategy, SaveStrategy


class ImportStrategy:
    def execute(self, network: str, content: str) -> Strategy:
        try:
            post = frontmatter.loads(content)
        except Exception as error:
            raise InvalidStrategy("o arquivo não é um markdown com cabeçalho name/description") from error
        name = str(post.metadata.get("name", "")).strip()
        if not name:
            raise InvalidStrategy("o arquivo precisa de name e description no cabeçalho")
        return SaveStrategy().execute(network, name, str(post.metadata.get("description", "")), post.content)
