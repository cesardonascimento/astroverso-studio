from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.models import Generation, Output
from app.services.catalog import AUTO_STRATEGY, GetNetwork
from app.services.events import RecordEvent
from app.services.jobs import EnqueueJob


class InvalidRequest(ValueError):
    pass


@dataclass
class Target:
    network: str
    strategy: str = AUTO_STRATEGY
    options: dict = field(default_factory=dict)


class CreateGeneration:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, instance: str, algorithm_id: str, inputs: dict, targets: list[Target]) -> Generation:
        algorithm = get_algorithm(algorithm_id)
        clean_inputs = {key: str(value).strip() for key, value in inputs.items() if str(value or "").strip()}
        missing = [item.label for item in algorithm.fields if item.required and item.name not in clean_inputs]
        if missing:
            raise InvalidRequest("preencha: " + ", ".join(missing))
        if not targets:
            raise InvalidRequest("escolha pelo menos uma rede")
        generation = Generation(instance=instance, algorithm=algorithm.id, inputs=clean_inputs)
        for target in targets:
            self._validate(target)
            generation.outputs.append(Output(network=target.network, strategy=target.strategy,
                                             options=target.options))
        self.session.add(generation)
        self.session.flush()
        RecordEvent(self.session).execute(generation.id, "pedido", "geração criada")
        EnqueueJob(self.session).execute(instance, generation.id, algorithm.preparation[0].name)
        return generation

    def _validate(self, target: Target) -> None:
        network = GetNetwork().execute(target.network)
        names = {strategy.name for strategy in network.strategies}
        if target.strategy != AUTO_STRATEGY and target.strategy not in names:
            raise InvalidRequest(f"estratégia desconhecida para {network.name}: {target.strategy}")
