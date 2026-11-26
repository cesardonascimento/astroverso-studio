from app.services.catalog import ListStrategies, Strategy


class GetStrategy:
    def execute(self, network: str, name: str) -> Strategy:
        strategy = next((item for item in ListStrategies().execute(network) if item.name == name), None)
        if strategy is None:
            raise LookupError(f"estratégia {name} não encontrada em {network}")
        return strategy
