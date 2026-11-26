from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def _session_factory(url: str) -> sessionmaker[Session]:
    return sessionmaker(create_engine_for(url), expire_on_commit=False)


@contextmanager
def open_session(url: str) -> Iterator[Session]:
    session = _session_factory(url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
