import re
from pathlib import Path

from app.config import Settings

REPO = Path(__file__).resolve().parents[2]
COMPOSE_ONLY = {"STUDIO_PORT", "WORK_DATA_DIR", "STORAGE_BIND_ADDRESS", "DATABASE_DATA_DIR", "S3_PORT", "S3_DATA_DIR"}


def env_example_keys() -> set[str]:
    lines = (REPO / ".env.example").read_text().splitlines()
    return {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}


def test_every_setting_is_listed():
    settings_keys = {name.upper() for name in Settings.model_fields}
    assert settings_keys - env_example_keys() == set()


def test_every_listed_variable_is_used():
    settings_keys = {name.upper() for name in Settings.model_fields}
    assert env_example_keys() - settings_keys - COMPOSE_ONLY == set()


def test_compose_only_uses_listed_variables():
    used = set(re.findall(r"\$\{(\w+)", (REPO / "compose.yaml").read_text()))
    assert used - env_example_keys() == set()


def test_environment_is_read_only_in_config():
    offenders = [path.name for path in (REPO / "studio" / "app").rglob("*.py")
                 if path.name != "config.py" and re.search(r"os\.environ|getenv", path.read_text())]
    assert offenders == []
