from pathlib import Path

from app.algorithms.base import PlanEditor, StepFailed
from app.algorithms.corte.load_transcript import LoadTranscript
from app.algorithms.corte.snap_segments import SnapSegments
from app.models import Generation

TEXT_FIELDS = ("title", "hook_text", "caption")


class ApplyCutPlanEdits(PlanEditor):
    def execute(self, generation: Generation, plan: dict, form: dict[str, list[str]], workspace: Path) -> dict:
        edited = {**plan, **{key: self._first(form, key) for key in TEXT_FIELDS if key in form}}
        if "hashtags" in form:
            edited["hashtags"] = [tag.lstrip("#") for tag in self._first(form, "hashtags").split() if tag.strip("#")]
        segments = self._edited_segments(plan["segments"], form)
        if segments != plan["segments"]:
            words = LoadTranscript().execute(generation, workspace)
            duration = float(generation.source.get("duration_s") or 1e9)
            edited["segments"] = [self._keep_or_snap(segment, plan["segments"], words, duration)
                                  for segment in segments]
            edited["segments"] = [segment for segment in edited["segments"] if segment]
            if not edited["segments"]:
                raise StepFailed("os trechos editados não têm fala")
            edited["duration_s"] = round(sum(item["end"] - item["start"] for item in edited["segments"]), 2)
        return edited

    def _edited_segments(self, segments: list[dict], form: dict[str, list[str]]) -> list[dict]:
        starts, ends = form.get("segment_start", []), form.get("segment_end", [])
        removed = set(form.get("segment_remove", []))
        if not starts:
            return segments
        result = []
        for index, (start, end) in enumerate(zip(starts, ends)):
            if str(index) in removed:
                continue
            original = segments[index] if index < len(segments) else {}
            start_value, end_value = float(start.replace(",", ".")), float(end.replace(",", "."))
            if end_value <= start_value:
                raise StepFailed(f"o trecho {index + 1} termina antes de começar")
            if original and (round(original["start"], 1), round(original["end"], 1)) == (start_value, end_value):
                result.append(original)
            else:
                result.append({"start": start_value, "end": end_value, "purpose": original.get("purpose", "")})
        return result

    def _keep_or_snap(self, segment: dict, previous: list[dict], words, duration: float) -> dict | None:
        if segment in previous:
            return segment
        snapped = SnapSegments().execute([segment], words, duration)
        return snapped[0] if snapped else None

    def _first(self, form: dict[str, list[str]], key: str) -> str:
        return (form.get(key) or [""])[0].strip()
