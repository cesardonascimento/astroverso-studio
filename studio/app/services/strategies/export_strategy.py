import frontmatter

from app.services.strategies.get_strategy import GetStrategy


class ExportStrategy:
    def execute(self, network: str, name: str) -> str:
        strategy = GetStrategy().execute(network, name)
        post = frontmatter.Post(strategy.text + "\n", name=strategy.name, description=strategy.description)
        return frontmatter.dumps(post, sort_keys=False) + "\n"
