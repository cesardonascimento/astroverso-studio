import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config import APP_DIR, settings
from app.lib.database.migrate import MigrateDatabase
from app.models import Base


@pytest.fixture(scope="session")
def database_url() -> str:
    config = settings()
    test_name = f"{config.database_name}_test"
    admin = create_engine(config.database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{test_name}"'))
    admin.dispose()
    url = config.database_url.rsplit("/", 1)[0] + f"/{test_name}"
    MigrateDatabase(APP_DIR.parent / "alembic.ini").execute(url)
    return url


@pytest.fixture
def session(database_url: str):
    engine = create_engine(database_url)
    with engine.begin() as connection:
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with Session(engine, expire_on_commit=False) as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture
def client(session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.controllers.database import database
    from app.main import app

    def test_database():
        yield session
        session.commit()

    app.dependency_overrides[database] = test_database
    test_client = TestClient(app)
    test_client.post("/login", data={"password": settings().studio_password})
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_bucket(monkeypatch):
    from app.dependencies import storage_client
    from app.lib.s3 import EnsureBucket

    monkeypatch.setattr(settings(), "s3_bucket", f"{settings().s3_bucket}-test")
    EnsureBucket(storage_client()).execute(settings().s3_bucket)
    return settings().s3_bucket
