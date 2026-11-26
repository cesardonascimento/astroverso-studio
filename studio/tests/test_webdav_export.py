import uuid

import pytest
from sqlalchemy import select

from app.config import settings
from app.dependencies import webdav_connection
from app.lib.webdav import CheckWebdavConnection, EnsureFolder, FileExists, UploadToWebdav, WebdavConnection
from app.models import Export, ExportState, Job
from app.worker import ClaimJob, RunJob
from tests.test_web_result import done_output


@pytest.fixture
def folder(monkeypatch):
    name = f"teste-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(settings(), "webdav_dir", f"Studio/{name}")
    return f"Studio/{name}"


def test_lib_creates_folders_uploads_and_checks(folder):
    connection = webdav_connection()
    EnsureFolder(connection).execute(f"{folder}/a/b")
    UploadToWebdav(connection).execute(b"ola", f"{folder}/a/b/x y.txt", "text/plain")
    assert FileExists(connection).execute(f"{folder}/a/b/x y.txt")
    assert not FileExists(connection).execute(f"{folder}/a/b/nada.txt")
    assert CheckWebdavConnection(connection).execute() == ""
    wrong = WebdavConnection(connection.url, connection.user, "errada")
    assert CheckWebdavConnection(wrong).execute() == "usuário ou senha recusados"


def test_export_sends_video_and_caption_without_overwriting(client, session, database_url, test_bucket, folder,
                                                           tmp_path):
    output = done_output(session, tmp_path)
    for _ in range(2):
        client.post(f"/outputs/{output.id}/export")
        job = ClaimJob(session).execute(output.generation.instance)
        session.commit()
        RunJob(database_url, tmp_path).execute(job.id)
        session.expire_all()
    exports = session.scalars(select(Export).order_by(Export.id)).all()
    assert [export.state for export in exports] == [ExportState.DONE, ExportState.DONE]
    first, second = exports[0].remote_path, exports[1].remote_path
    assert first.endswith(" - Título.mp4") and second.endswith(" - Título (2).mp4")
    connection = webdav_connection()
    with connection.client() as http:
        assert http.get(connection.address(first.replace(".mp4", ".txt"))).text == "legenda\n\n#a #b\n"
        assert len(http.get(connection.address(first)).content) == 10240
    page = client.get(f"/generations/{output.generation_id}").text
    assert "Enviado:" in page


def test_export_failure_keeps_video_done(client, session, database_url, test_bucket, folder, tmp_path, monkeypatch):
    output = done_output(session, tmp_path)
    monkeypatch.setattr(settings(), "webdav_password", "errada")
    client.post(f"/outputs/{output.id}/export")
    job = session.scalars(select(Job)).one()
    job.max_attempts = 1
    session.commit()
    job = ClaimJob(session).execute(output.generation.instance)
    session.commit()
    RunJob(database_url, tmp_path).execute(job.id)
    session.expire_all()
    export = session.scalars(select(Export)).one()
    assert export.state == ExportState.FAILED and "401" in export.last_error
    assert session.get(type(output), output.id).state == "DONE"


def test_settings_page_masks_secrets(client):
    page = client.get("/settings").text
    assert "Modelo do Claude" in page and settings().webdav_password not in page and "••••" in page


def test_settings_webdav_check(client):
    assert "Conectado" in client.post("/settings/webdav-test").text
