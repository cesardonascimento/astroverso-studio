from sqlalchemy.orm import Session

from app.algorithms.base import Step, StepContext, StepFailed
from app.algorithms.corte.build_prompt import BuildCutPrompt
from app.algorithms.corte.cut_plan import CutPlan
from app.algorithms.corte.load_transcript import LoadTranscript
from app.algorithms.corte.snap_segments import KeepUnchangedSegments, SnapSegments
from app.config import settings
from app.dependencies import generate_structured
from app.models import Output, OutputVersion, VersionKind
from app.services.catalog import AUTO_STRATEGY, GetNetwork, Network
from app.services.costs import RecordLlmCall


class PlanCut(Step):
    name = "plan"
    label = "Roteiro"

    def execute(self, context: StepContext) -> str:
        output, generation = context.output, context.generation
        network = GetNetwork().execute(output.network)
        words = LoadTranscript().execute(generation, context.workspace)
        pending = output.pending_request or {}
        kind = pending.get("kind") or (VersionKind.REPLAN if output.current_version else VersionKind.INITIAL)
        current = output.versions[-1].plan if output.versions else None
        prompt = BuildCutPrompt().execute(generation, network, output.strategy, words, kind, pending.get("text"),
                                          current)
        result = generate_structured().execute(prompt.system, prompt.user, CutPlan)
        RecordLlmCall(context.session).execute(generation, f"corte.{kind}", result.usage)
        plan = result.value.model_dump()
        duration = float(generation.source.get("duration_s") or 1e9)
        segments = plan["segments"]
        plan["segments"] = (KeepUnchangedSegments().execute(segments, current.get("segments", []), words, duration)
                            if kind == VersionKind.REVISION and current else
                            SnapSegments().execute(segments, words, duration))
        if not plan["segments"]:
            raise StepFailed("o roteiro não tem trechos válidos")
        plan.update(duration_s=round(sum(item["end"] - item["start"] for item in plan["segments"]), 2),
                    prompt_version=prompt.version, model=settings().llm_model)
        self._save_version(context.session, output, network, plan, kind, pending.get("text"))
        return f"roteiro v{output.current_version}: {plan['title']} ({plan['duration_s']:.0f} s)"

    def _save_version(self, session: Session, output: Output, network: Network, plan: dict, kind: str,
                      request: str | None) -> None:
        strategy_name = output.strategy if output.strategy != AUTO_STRATEGY else plan["strategy"]
        strategy = next((item for item in network.strategies if item.name == strategy_name), None)
        output.current_version += 1
        output.pending_request = None
        output.versions.append(OutputVersion(version=output.current_version, kind=kind, request=request, plan=plan,
                                             strategy_name=strategy.name if strategy else strategy_name,
                                             strategy_text=strategy.text if strategy else ""))
