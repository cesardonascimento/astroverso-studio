from sqlalchemy.orm import Session

from app.dependencies import webdav_connection
from app.models import Export, ExportState, Output
from app.services.jobs import EnqueueJob
from app.services.outputs import ActionNotAllowed

EXPORT_STEP = "export"


class RequestExport:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output: Output) -> Export | None:
        if webdav_connection() is None:
            return None
        version = next((item for item in reversed(output.versions) if item.video_key), None)
        if version is None:
            raise ActionNotAllowed("ainda não há vídeo para enviar")
        export = Export(output_version_id=version.id, target="webdav", state=ExportState.PENDING)
        self.session.add(export)
        EnqueueJob(self.session).execute(output.generation.instance, output.generation_id, EXPORT_STEP, output.id)
        return export
