from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Generation, Output


class StepFailed(RuntimeError):
    pass


@dataclass
class InputField:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    help: str = ""


@dataclass
class StepContext:
    session: Session
    generation: Generation
    workspace: Path
    output: Output | None = None


class Step:
    name: str = ""
    label: str = ""

    def execute(self, context: StepContext) -> str:
        raise NotImplementedError


@dataclass
class Algorithm:
    id: str
    name: str
    description: str
    fields: list[InputField]
    preparation: list[type[Step]]
    planning: type[Step]
    rendering: list[type[Step]] = field(default_factory=list)

    def step_named(self, name: str) -> type[Step]:
        for step in [*self.preparation, self.planning, *self.rendering]:
            if step.name == name:
                return step
        raise LookupError(f"etapa desconhecida no algoritmo {self.id}: {name}")

    def step_after(self, name: str) -> type[Step] | None:
        for steps in (self.preparation, self.rendering):
            names = [step.name for step in steps]
            if name in names:
                index = names.index(name)
                return steps[index + 1] if index + 1 < len(steps) else None
        return None
