from datetime import datetime, timezone

from sqlalchemy import select

from app.dependencies import upload_file
from app.models import Generation, Job, Output, OutputState
from app.services.outputs import BuildVideoName
from tests.factories import awaiting_approval


def done_output(session, tmp_path):
    output = awaiting_approval(session)
    video = tmp_path / "final.mp4"
    video.write_bytes(bytes(range(256)) * 40)
    version = output.versions[-1]
    version.video_key = upload_file().execute(video, f"outputs/{output.id}/v1/final.mp4", "video/mp4")
    version.render_report = {"layout": "fit_blur", "subtitle_preset": "padrao", "subtitle_events": 3}
    output.state = OutputState.DONE
    session.commit()
    return output


def test_player_receives_partial_content(client, session, test_bucket, tmp_path):
    output = done_output(session, tmp_path)
    response = client.get(f"/outputs/{output.id}/videos/1", headers={"Range": "bytes=0-99"})
    assert response.status_code == 206 and len(response.content) == 100
    assert response.headers["content-range"] == "bytes 0-99/10240"


def test_download_uses_timestamp_and_title(client, session, test_bucket, tmp_path):
    output = done_output(session, tmp_path)
    response = client.get(f"/outputs/{output.id}/videos/1?download=1")
    assert response.status_code == 200 and len(response.content) == 10240
    assert "T%C3%ADtulo.mp4" in response.headers["content-disposition"]


def test_video_name_format():
    version = type("V", (), {"created_at": datetime(2026, 11, 26, 17, 5, tzinfo=timezone.utc),
                             "plan": {"title": 'Ele: "largou" tudo?'}})()
    assert BuildVideoName("America/Sao_Paulo").execute(version) == "202611261405 - Ele largou tudo"


def test_result_page_has_player_and_actions(client, session, test_bucket, tmp_path):
    output = done_output(session, tmp_path)
    page = client.get(f"/generations/{output.generation_id}").text
    assert "<video" in page and "Pedir alteração" in page and "Renderizar de novo" in page


def test_revise_goes_straight_to_planning_as_revision(client, session, test_bucket, tmp_path):
    output = done_output(session, tmp_path)
    client.post(f"/outputs/{output.id}/revise", data={"text": "legenda maior"})
    session.expire_all()
    output = session.get(Output, output.id)
    assert output.pending_request == {"kind": "revision", "text": "legenda maior"} and output.state == "PLANNING"


def test_rerender_creates_version_with_new_visual(client, session, test_bucket, tmp_path):
    output = done_output(session, tmp_path)
    client.post(f"/outputs/{output.id}/rerender", data={"layout": "crop", "subtitle_preset": "grande"})
    session.expire_all()
    output = session.get(Output, output.id)
    assert output.current_version == 2 and output.versions[-1].plan["render"]["layout"] == "crop"
    assert session.scalars(select(Job)).one().step == "render"


def test_delete_original_removes_file_and_blocks_new_renders(client, session, test_bucket, tmp_path):
    output = done_output(session, tmp_path)
    generation = output.generation
    original = tmp_path / "o.mp4"
    original.write_bytes(b"x")
    generation.original_key = upload_file().execute(original, f"generations/{generation.id}/original.mp4")
    session.commit()
    client.post(f"/generations/{generation.id}/delete-original")
    session.expire_all()
    generation = session.get(Generation, generation.id)
    assert generation.original_key is None and generation.original_deleted_at is not None


def test_list_filters_by_state(client, session):
    awaiting_approval(session)
    assert "Vídeo" in client.get("/generations?state=approval").text
    assert "Nada por aqui" in client.get("/generations?state=done").text
