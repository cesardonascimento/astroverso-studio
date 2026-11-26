from app.lib.content import MarkdownDocument, WriteMarkdown
from app.services.catalog import AUTO_STRATEGY, GetNetwork, Strategy
from app.services.strategies.strategy_path import slugify, strategy_path


class InvalidStrategy(ValueError):
    pass


class SaveStrategy:
    def execute(self, network: str, name: str, description: str, text: str, previous_name: str = "") -> Strategy:
        GetNetwork().execute(network)
        slug = slugify(name)
        if not slug or slug == AUTO_STRATEGY:
            raise InvalidStrategy("escolha outro nome (letras, números e hífen; não pode ser auto)")
        if not description.strip() or not text.strip():
            raise InvalidStrategy("preencha a descrição e o texto")
        target = strategy_path(network, slug)
        if target.exists() and slug != slugify(previous_name):
            raise InvalidStrategy(f"já existe uma estratégia chamada {slug}")
        WriteMarkdown().execute(MarkdownDocument(path=target, meta={"name": slug, "description": description.strip()},
                                                 body=text.strip()))
        if previous_name and slugify(previous_name) != slug:
            strategy_path(network, previous_name).unlink(missing_ok=True)
        return Strategy(network=network, name=slug, description=description.strip(), text=text.strip())
