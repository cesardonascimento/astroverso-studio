from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import download_file, webdav_connection
from app.lib.webdav import EnsureFolder, FileExists, UploadToWebdav
from app.models import Export, ExportState, Output, OutputVersion
from app.services.outputs import BuildVideoName


class ExportVersion:
    def __init__(self, session: Session, workspace: Path):
        self.session = session
        self.workspace = workspace

    def execute(self, output: Output) -> str:
        connection = webdav_connection()
        if connection is None:
            raise RuntimeError("WebDAV não configurado (WEBDAV_URL vazio)")
        export = self.session.scalars(select(Export).join(OutputVersion)
                                      .where(OutputVersion.output_id == output.id, Export.state == ExportState.PENDING)
                                      .order_by(Export.id.desc()).limit(1)).first()
        if export is None:
            return "nada pendente para enviar"
        version = self.session.get(OutputVersion, export.output_version_id)
        folder = settings().webdav_dir.strip("/")
        EnsureFolder(connection).execute(folder)
        name = self._free_name(connection, folder, BuildVideoName(settings().tz).execute(version))
        video = self.workspace / "exports" / f"{version.id}.mp4"
        download_file().execute(version.video_key, video)
        UploadToWebdav(connection).execute(video, f"{folder}/{name}.mp4", "video/mp4")
        UploadToWebdav(connection).execute(self._post_text(version).encode(), f"{folder}/{name}.txt",
                                           "text/plain; charset=utf-8")
        video.unlink(missing_ok=True)
        export.state = ExportState.DONE
        export.remote_path = f"{folder}/{name}.mp4"
        export.last_error = None
        return f"enviado para {export.remote_path}"

    def _free_name(self, connection, folder: str, base: str) -> str:
        name, counter = base, 2
        while FileExists(connection).execute(f"{folder}/{name}.mp4"):
            name, counter = f"{base} ({counter})", counter + 1
        return name

    def _post_text(self, version: OutputVersion) -> str:
        hashtags = " ".join("#" + tag.lstrip("#") for tag in version.plan.get("hashtags", []))
        return f"{version.plan.get('caption', '')}\n\n{hashtags}\n"
