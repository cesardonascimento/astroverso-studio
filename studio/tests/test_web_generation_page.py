import json

from sqlalchemy import select

from app.algorithms.corte.apply_plan_edits import ApplyCutPlanEdits
from app.models import Job, Output, OutputVersion
from tests.factories import PLAN, awaiting_approval


def test_page_shows_plan_for_approval(client, session):
    output = awaiting_approval(session)
    page = client.get(f"/generations/{output.generation_id}").text
    assert "Aprovar e renderizar" in page and "olha isso" in page and "estratégia viral" in page


def test_approve_with_text_edits_creates_version_and_queues_render(client, session):
    output = awaiting_approval(session)
    response = client.post(f"/outputs/{output.id}/approve", data={
        "title": "Novo título", "hook_text": "olha isso", "caption": "legenda", "hashtags": "#a #b #c",
        "segment_start": ["1.9", "9.9"], "segment_end": ["6.2", "14.2"]}, follow_redirects=False)
    assert response.status_code == 303
    session.expire_all()
    output = session.get(Output, output.id)
    assert output.state == "RENDERING" and output.current_version == 2
    assert output.versions[-1].plan["title"] == "Novo título" and output.versions[-1].plan["hashtags"] == ["a", "b", "c"]
    assert output.versions[-1].plan["segments"] == PLAN["segments"]
    assert session.scalars(select(Job)).one().step == "render"


def test_approve_without_changes_keeps_version(client, session):
    output = awaiting_approval(session)
    client.post(f"/outputs/{output.id}/approve", data={"title": "Título", "hook_text": "olha isso",
                                                        "caption": "legenda", "hashtags": "#a #b"})
    session.expire_all()
    assert session.get(Output, output.id).current_version == 1


def test_approve_twice_is_refused(client, session):
    output = awaiting_approval(session)
    client.post(f"/outputs/{output.id}/approve", data={})
    page = client.post(f"/outputs/{output.id}/approve", data={}).text
    assert "não está aguardando aprovação" in page


def test_replan_queues_new_plan_with_request(client, session):
    output = awaiting_approval(session)
    client.post(f"/outputs/{output.id}/replan", data={"text": "mais curto"})
    session.expire_all()
    output = session.get(Output, output.id)
    assert output.state == "PLANNING" and output.pending_request == {"kind": "replan", "text": "mais curto"}
    assert session.scalars(select(Job)).one().step == "plan"


def test_cancel_output(client, session):
    output = awaiting_approval(session)
    client.post(f"/outputs/{output.id}/cancel")
    session.expire_all()
    assert session.get(Output, output.id).state == "CANCELLED"


def test_busy_output_card_keeps_polling(client, session):
    output = awaiting_approval(session)
    output.state = "RENDERING"
    session.commit()
    card = client.get(f"/outputs/{output.id}/card").text
    assert 'hx-trigger="every 3s"' in card


def test_editor_snaps_changed_segment_to_words(session, tmp_path):
    output = awaiting_approval(session)
    generation = output.generation
    folder = tmp_path / "generations" / str(generation.id)
    folder.mkdir(parents=True)
    words = [{"text": f"w{i}", "start": i * 1.0, "end": i * 1.0 + 0.8} for i in range(20)]
    (folder / "transcript.json").write_text(json.dumps(words))
    edited = ApplyCutPlanEdits().execute(generation, PLAN, {"segment_start": ["1.9", "15"], "segment_end": ["6.2", "18"]},
                                         tmp_path)
    assert edited["segments"][0] == PLAN["segments"][0]
    assert edited["segments"][1]["text"] == "w15 w16 w17" and edited["segments"][1]["start"] == 14.9
