from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.config import settings
from app.lib.database import open_session


def database() -> Iterator[Session]:
    with open_session(settings().database_url) as session:
        yield session
