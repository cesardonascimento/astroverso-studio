from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    media_dir: Path = Path("/data/media")
    prompts_dir: Path = Path("/app/prompts")
    migrations_dir: Path = Path("/app/migrations")

    worker_token: str
    worker_concurrency: int = 1
    content_language: str = "pt-BR"

    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"
    llm_model_fast: str = "claude-opus-5-5"
    llm_trend_web_search: bool = False

    # transcrição local (quando o YouTube não tem legenda)
    whisper_model: str = "small"  # tiny | base | small | medium | large-v3
    whisper_device: str = "cpu"

    # cortes
    cut_max_duration_s: int = 75
    cut_layout: str = "auto"  # auto | crop | fit_blur
    youtube_cookies_file: str = ""  # opcional, se o YouTube pedir login


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


LLM_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
WEB_SEARCH_PRICE_PER_REQUEST = 0.01


def presets() -> dict:
    """config/presets.json — relido a cada uso (dá para editar sem reiniciar)."""
    import json

    path = Path("/app/config/presets.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"defaults": {}, "subtitles": {}}


def subtitle_style(name: str | None) -> tuple[str, dict]:
    p = presets()
    name = name or p.get("defaults", {}).get("subtitle_preset") or "padrao"
    subs = p.get("subtitles", {})
    if name not in subs:
        name = next(iter(subs), "padrao")
    return name, subs.get(name, {})
