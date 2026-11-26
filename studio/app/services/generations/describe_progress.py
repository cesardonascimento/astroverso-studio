from dataclasses import dataclass

from app.algorithms import get_algorithm
from app.models import Generation, GenerationState, Output, OutputState


@dataclass
class ProgressStep:
    label: str
    status: str


OUTPUT_ORDER = [OutputState.PLANNING, OutputState.AWAITING_APPROVAL, OutputState.RENDERING, OutputState.DONE]


class DescribeProgress:
    def execute(self, generation: Generation, output: Output | None = None) -> list[ProgressStep]:
        if output is None:
            return self._preparation(generation)
        return self._output(output)

    def _preparation(self, generation: Generation) -> list[ProgressStep]:
        algorithm = get_algorithm(generation.algorithm)
        done_labels = {event.step for event in generation.events if event.ok}
        steps, active_found = [], False
        for step in algorithm.preparation:
            if step.label in done_labels:
                status = "done"
            elif generation.state == GenerationState.FAILED and not active_found:
                status, active_found = "failed", True
            elif generation.state == GenerationState.PREPARING and not active_found:
                status, active_found = "active", True
            else:
                status = "pending"
            steps.append(ProgressStep(step.label, status))
        return steps

    def _output(self, output: Output) -> list[ProgressStep]:
        labels = ["Roteiro", "Aprovação", "Render", "Pronto"]
        if output.state in (OutputState.WAITING, OutputState.CANCELLED):
            return [ProgressStep(label, "pending") for label in labels]
        if output.state == OutputState.FAILED:
            position = 2 if output.approved_at else 0
            return [ProgressStep(label, "done" if index < position else "failed" if index == position else "pending")
                    for index, label in enumerate(labels)]
        position = OUTPUT_ORDER.index(output.state)
        return [ProgressStep(label, "done" if index < position or output.state == OutputState.DONE else
                             "active" if index == position else "pending") for index, label in enumerate(labels)]
