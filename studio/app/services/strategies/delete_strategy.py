from app.services.catalog import ListStrategies
from app.services.strategies.save_strategy import InvalidStrategy
from app.services.strategies.strategy_path import strategy_path


class DeleteStrategy:
    def execute(self, network: str, name: str) -> None:
        if len(ListStrategies().execute(network)) <= 1:
            raise InvalidStrategy("a rede precisa de pelo menos uma estratégia")
        strategy_path(network, name).unlink(missing_ok=True)
