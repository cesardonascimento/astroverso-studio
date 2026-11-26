from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.models import OutputState, OutputVersion, VersionKind
from app.services.events import RecordEvent
from app.services.jobs import EnqueueJob
from app.services.outputs.action_not_allowed import ActionNotAllowed
from app.services.outputs.load_output import LoadOutput

LAYOUTS = {"auto", "crop", "fit_blur"}


class RerenderOutput:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int, layout: str, subtitle_preset: str) -> None:
        output = LoadOutput(self.session).execute(output_id)
        if output.state not in (OutputState.DONE, OutputState.FAILED) or not output.versions:
            raise ActionNotAllowed("só dá para renderizar de novo um vídeo pronto ou que falhou")
        if layout not in LAYOUTS:
            raise ActionNotAllowed(f"enquadramento desconhecido: {layout}")
        current = output.versions[-1]
        plan = {**current.plan, "render": {"layout": layout, "subtitle_preset": subtitle_preset, "crop_x": -1}}
        output.current_version += 1
        output.versions.append(OutputVersion(version=output.current_version, kind=VersionKind.RERENDER,
                                             request=f"enquadramento {layout}, legenda {subtitle_preset}", plan=plan,
                                             strategy_name=current.strategy_name, strategy_text=current.strategy_text))
        output.state = OutputState.RENDERING
        output.last_error = None
        generation = output.generation
        RecordEvent(self.session).execute(generation.id, "Render pedido",
                                          f"v{output.current_version}: enquadramento {layout}, legenda {subtitle_preset}",
                                          output.id)
        EnqueueJob(self.session).execute(generation.instance, generation.id,
                                         get_algorithm(generation.algorithm).rendering[0].name, output.id)
