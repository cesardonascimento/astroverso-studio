from sqlalchemy import select

from app.models import Generation, Job


def test_form_lists_algorithm_network_and_strategies(client):
    page = client.get("/generations/new").text
    assert "Corte de vídeo" in page and "TikTok" in page and "viral" in page and "Auto" in page


def test_submitting_creates_generation_with_targets(client, session):
    response = client.post("/generations", data={
        "algorithm": "corte", "input.url": "https://youtu.be/x", "input.instructions": "foca no fim",
        "network": "tiktok", "strategy.tiktok": "emotivo", "layout.tiktok": "fit_blur", "subtitle.tiktok": "grande",
        "auto_approve.tiktok": "1"}, follow_redirects=False)
    generation = session.scalars(select(Generation)).one()
    assert response.status_code == 303 and response.headers["location"] == f"/generations/{generation.id}"
    output = generation.outputs[0]
    assert generation.inputs == {"url": "https://youtu.be/x", "instructions": "foca no fim"}
    assert (output.strategy, output.options) == ("emotivo", {"layout": "fit_blur", "subtitle_preset": "grande",
                                                             "auto_approve": True})
    assert session.scalars(select(Job)).one().step == "download"


def test_missing_link_shows_error_and_keeps_values(client):
    response = client.post("/generations", data={"algorithm": "corte", "input.instructions": "algo",
                                                 "network": "tiktok", "strategy.tiktok": "auto"})
    assert response.status_code == 422 and "preencha: Link do YouTube" in response.text and "algo" in response.text
