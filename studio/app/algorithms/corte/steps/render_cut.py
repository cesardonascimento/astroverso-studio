from app.algorithms.base import Step, StepContext
from app.algorithms.corte.ensure_local_original import EnsureLocalOriginal
from app.algorithms.corte.files import render_dir, video_key
from app.algorithms.corte.load_transcript import LoadTranscript
from app.algorithms.corte.render_settings import ResolveRenderSettings
from app.dependencies import upload_file
from app.lib.ffmpeg import RenderVerticalCut
from app.lib.media import Segment
from app.services.catalog import GetNetwork, GetSubtitlePreset


class RenderCut(Step):
    name = "render"
    label = "Render"

    def execute(self, context: StepContext) -> str:
        output, generation = context.output, context.generation
        version = output.versions[-1]
        settings = ResolveRenderSettings().execute(GetNetwork().execute(output.network), output.options, version.plan)
        preset = GetSubtitlePreset().execute(settings["subtitle_preset"])
        cut = RenderVerticalCut(preset.style).execute(
            EnsureLocalOriginal().execute(generation, context.workspace),
            [Segment(item["start"], item["end"]) for item in version.plan["segments"]],
            LoadTranscript().execute(generation, context.workspace),
            render_dir(context.workspace, output.id, version.version),
            version.plan.get("hook_text", ""), settings["layout"], settings)
        version.video_key = upload_file().execute(cut.path, video_key(output.id, version.version), "video/mp4")
        version.duration_s = round(cut.duration, 2)
        version.render_report = {"layout": cut.layout, "subtitle_preset": preset.name,
                                 "subtitle_events": cut.subtitle_events}
        return f"{cut.duration:.0f} s, layout {cut.layout}, legenda {preset.name}"
