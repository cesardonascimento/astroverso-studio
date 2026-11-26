from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).parent
CONTENT_DIR = APP_DIR.parent / "content"
WORK_DIR = Path("/data/work")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    instance_name: str
    studio_password: str
    secret_key: str
    tz: str = "UTC"
    content_language: str = "pt-BR"

    database_host: str
    database_port: int = 5432
    database_name: str
    database_user: str
    database_password: str

    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str

    anthropic_api_key: str
    llm_model: str = "claude-opus-5-5"

    whisper_model: str = "medium"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    youtube_cookies_file: str = ""

    webdav_url: str = ""
    webdav_user: str = ""
    webdav_password: str = ""
    webdav_dir: str = "Studio"

    @property
    def database_url(self) -> str:
        return (f"postgresql+psycopg://{self.database_user}:{self.database_password}"
                f"@{self.database_host}:{self.database_port}/{self.database_name}")


@lru_cache
def settings() -> Settings:
    return Settings()
