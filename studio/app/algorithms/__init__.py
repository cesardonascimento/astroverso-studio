from app.algorithms.base import Algorithm
from app.algorithms.corte.algorithm import CORTE

ALGORITHMS: dict[str, Algorithm] = {algorithm.id: algorithm for algorithm in (CORTE,)}


def get_algorithm(algorithm_id: str) -> Algorithm:
    if algorithm_id not in ALGORITHMS:
        raise LookupError(f"algoritmo desconhecido: {algorithm_id}")
    return ALGORITHMS[algorithm_id]
