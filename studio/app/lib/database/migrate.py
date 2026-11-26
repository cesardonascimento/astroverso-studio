import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


class MigrateDatabase:
    def __init__(self, alembic_ini: Path):
        self.alembic_ini = alembic_ini

    def execute(self, url: str) -> None:
        self._wait_until_reachable(url)
        config = Config(str(self.alembic_ini))
        config.set_main_option("script_location", str(self.alembic_ini.parent / "migrations"))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(config, "head")

    def _wait_until_reachable(self, url: str, attempts: int = 30) -> None:
        engine = create_engine(url)
        try:
            for attempt in range(attempts):
                try:
                    with engine.connect() as connection:
                        connection.execute(text("SELECT 1"))
                    return
                except OperationalError:
                    if attempt == attempts - 1:
                        raise
                    time.sleep(2)
        finally:
            engine.dispose()
