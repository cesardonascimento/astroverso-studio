from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    media_dir: Path = Path("/data/media")
    prompts_dir: Path = Path("/app/prompts")
    config_dir: Path = Path("/app/config")
    migrations_dir: Path = Path("/app/migrations")

    worker_token: str
    worker_concurrency: int = 1
    content_language: str = "pt-BR"
    trend_country: str = "BR"

    llm_provider: str = "claude_code"  # claude_code (assinatura, via CLI) | anthropic (API)
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-5-5"
    llm_model_fast: str = "claude-opus-5-5"
    llm_trend_web_search: bool = True

    trend_provider: str = "manual"
    apify_token: str = ""
    apify_trend_actor: str = "data_xplorer~tiktok-trends"

    tts_provider: str = "edge"
    tts_voice: str = "pt-BR-AntonioNeural"
    tts_rate: str = "+12%"

    image_provider: str = "placeholder"
    pexels_api_key: str = ""


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


# Preço por 1M tokens (entrada, saída) em USD — usado só para estimar custo.
# Fonte: tabela oficial de preços da Anthropic (nov/2026). Atualize se mudar.
LLM_PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
WEB_SEARCH_PRICE_PER_REQUEST = 0.01  # US$10 / 1.000 buscas
