from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import read_object
from app.lib.s3 import ObjectStream
from app.models import OutputVersion


@dataclass
class VideoStream:
    version: OutputVersion
    stream: ObjectStream


class OpenVideo:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int, version_number: int, byte_range: str | None) -> VideoStream:
        version = self.session.scalars(select(OutputVersion).where(OutputVersion.output_id == output_id,
                                                                   OutputVersion.version == version_number)).first()
        if version is None or not version.video_key:
            raise LookupError("vídeo não encontrado")
        return VideoStream(version=version, stream=read_object().execute(version.video_key, byte_range))
