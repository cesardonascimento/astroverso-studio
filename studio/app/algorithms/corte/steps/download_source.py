import json

from app.algorithms.base import Step, StepContext
from app.algorithms.corte.files import generation_dir, original_key
from app.dependencies import download_video, upload_file


class DownloadSource(Step):
    name = "download"
    label = "Download"

    def execute(self, context: StepContext) -> str:
        generation = context.generation
        directory = generation_dir(context.workspace, generation.id)
        video = download_video().execute(generation.inputs["url"], directory / "download")
        original = directory / "original.mp4"
        video.path.replace(original)
        (directory / "captions.json").write_text(
            json.dumps({"automatic": video.automatic_captions, "manual": video.subtitles}), encoding="utf-8")
        generation.original_key = upload_file().execute(original, original_key(generation.id), "video/mp4")
        generation.title = video.title
        generation.source = {"id": video.id, "title": video.title, "channel": video.channel,
                             "duration_s": video.duration_s, "language": video.language}
        return f"{video.title} ({video.duration_s / 60:.0f} min)"
