from app.algorithms.base import Step, StepContext, StepFailed
from app.algorithms.corte.files import render_dir
from app.dependencies import download_file
from app.lib.ffmpeg import CheckVideoQuality


class CheckCut(Step):
    name = "check"
    label = "Qualidade"

    def execute(self, context: StepContext) -> str:
        version = context.output.versions[-1]
        local = render_dir(context.workspace, context.output.id, version.version) / "final.mp4"
        if not local.exists():
            download_file().execute(version.video_key, local)
        report = CheckVideoQuality().execute(local, version.render_report.get("subtitle_events", 0))
        version.render_report = {**version.render_report, "quality": report.to_dict()}
        failed = [check.name for check in report.checks if not check.ok]
        if not report.passed:
            raise StepFailed("controle de qualidade reprovou: " + ", ".join(failed))
        return "aprovado" + (f" com avisos: {', '.join(failed)}" if failed else "")
