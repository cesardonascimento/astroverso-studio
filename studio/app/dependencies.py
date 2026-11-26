from botocore.client import BaseClient

from app.ai.claude import GenerateStructured
from app.ai.whisper import TranscribeAudio
from app.config import settings
from app.lib.s3 import DeleteObject, DownloadFile, ReadObject, UploadFile, s3_client
from app.lib.youtube import DownloadVideo


def storage_client() -> BaseClient:
    config = settings()
    return s3_client(config.s3_endpoint, config.s3_access_key, config.s3_secret_key)


def upload_file() -> UploadFile:
    return UploadFile(storage_client(), settings().s3_bucket)


def download_file() -> DownloadFile:
    return DownloadFile(storage_client(), settings().s3_bucket)


def read_object() -> ReadObject:
    return ReadObject(storage_client(), settings().s3_bucket)


def delete_object() -> DeleteObject:
    return DeleteObject(storage_client(), settings().s3_bucket)


def download_video() -> DownloadVideo:
    return DownloadVideo(settings().youtube_cookies_file)


def transcribe_audio() -> TranscribeAudio:
    config = settings()
    return TranscribeAudio(config.whisper_model, config.whisper_device, config.whisper_compute_type)


def generate_structured() -> GenerateStructured:
    config = settings()
    return GenerateStructured(config.anthropic_api_key, config.llm_model)
