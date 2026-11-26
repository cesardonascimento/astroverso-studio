import shutil

import pytest
from sqlalchemy import select

from app.ai.claude import ClaudeUsage, StructuredResult
from app.algorithms.corte.cut_plan import CutPlan
from app.config import settings
from app.dependencies import storage_client
from app.lib.media import Word
from app.lib.s3 import EnsureBucket, ReadObject
from app.lib.youtube import Captions, VideoInfo
from app.models import Event, Generation, Job, JobState, LlmCall, Output, OutputState
from app.services.generations import CreateGeneration, InvalidRequest, Target
from app.worker import ClaimJob, RunJob
from tests.test_ffmpeg import make_source

PLAN = {"strategy": "viral", "title": "Teste", "hook_text": "olha isso",
        "segments": [{"start": 2.0, "end": 6.0, "purpose": "gancho"}, {"start": 10.0, "end": 14.0, "purpose": "payoff"}],
        "caption": "legenda", "hashtags": ["a", "b", "c"], "why": "porque sim", "alternatives": [],
        "render": {"layout": "", "subtitle_preset": "", "crop_x": -1}, "changes": ""}


class FakeDownload:
    def __init__(self, source):
        self.source = source

    def execute(self, url, directory):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "source.mp4"
        shutil.copy(self.source, path)
        return VideoInfo(id="x", title="Vídeo de teste", channel="Canal", duration_s=20, language="pt", path=path)


class FakeCaptions:
    def execute(self, video):
        return Captions("youtube_auto:pt", [Word(f"palavra{i}.", i * 0.5, i * 0.5 + 0.4) for i in range(40)])


class FakeClaude:
    def execute(self, system, user, output):
        assert "ESTRATÉGIA" in system and "TRANSCRIÇÃO" in user
        return StructuredResult(CutPlan.model_validate(PLAN), ClaudeUsage("claude-opus-5-5", 1000, 200, 10))


@pytest.fixture
def fakes(monkeypatch, tmp_path):
    source = make_source(tmp_path / "source.mp4")
    monkeypatch.setattr("app.algorithms.corte.steps.download_source.download_video", lambda: FakeDownload(source))
    monkeypatch.setattr("app.algorithms.corte.steps.transcribe_source.FetchCaptions", FakeCaptions)
    monkeypatch.setattr("app.algorithms.corte.steps.plan_cut.generate_structured", lambda: FakeClaude())
    monkeypatch.setattr(settings(), "s3_bucket", f"{settings().s3_bucket}-test")
    EnsureBucket(storage_client()).execute(settings().s3_bucket)


def run_all(session, database_url, workspace, instance):
    while True:
        job = ClaimJob(session).execute(instance)
        session.commit()
        if job is None:
            return
        RunJob(database_url, workspace).execute(job.id)
        session.expire_all()


def test_auto_approved_cut_goes_from_link_to_video(session, database_url, fakes, tmp_path):
    generation = CreateGeneration(session).execute("a", "corte", {"url": "https://youtu.be/x"},
                                                   [Target("tiktok", "auto", {"auto_approve": True})])
    session.commit()

    run_all(session, database_url, tmp_path / "work", "a")

    generation = session.get(Generation, generation.id)
    output = generation.outputs[0]
    assert generation.state == "READY" and generation.title == "Vídeo de teste"
    assert output.state == OutputState.DONE, [event.message for event in generation.events]
    version = output.versions[0]
    assert version.strategy_name == "viral" and "Gancho" in version.strategy_text
    assert version.render_report["quality"]["passed"]
    stream = ReadObject(storage_client(), settings().s3_bucket).execute(version.video_key, "bytes=0-3")
    assert stream.total_size > 10000
    assert session.scalars(select(LlmCall)).one().cost_usd > 0
    assert [event.step for event in generation.events][:3] == ["pedido", "Download", "Transcrição"]


def test_plan_waits_for_approval_by_default(session, database_url, fakes, tmp_path):
    generation = CreateGeneration(session).execute("a", "corte", {"url": "x"}, [Target("tiktok", "viral")])
    session.commit()
    run_all(session, database_url, tmp_path / "work", "a")
    assert session.get(Output, generation.outputs[0].id).state == OutputState.AWAITING_APPROVAL


def test_other_instance_does_not_take_the_job(session, database_url, fakes, tmp_path):
    CreateGeneration(session).execute("a", "corte", {"url": "x"}, [Target("tiktok")])
    session.commit()
    assert ClaimJob(session).execute("b") is None
    assert session.scalars(select(Job)).one().state == JobState.QUEUED


def test_failure_is_retried_then_recorded(session, database_url, monkeypatch, tmp_path):
    class Broken:
        def execute(self, url, directory):
            raise RuntimeError("youtube fora do ar")

    monkeypatch.setattr("app.algorithms.corte.steps.download_source.download_video", lambda: Broken())
    generation = CreateGeneration(session).execute("a", "corte", {"url": "x"}, [Target("tiktok")])
    session.commit()
    job = ClaimJob(session).execute("a")
    session.commit()
    RunJob(database_url, tmp_path).execute(job.id)
    session.expire_all()
    job = session.get(Job, job.id)
    assert job.state == JobState.QUEUED and "youtube fora do ar" in job.last_error
    assert session.scalars(select(Event).where(Event.ok.is_(False))).one()


def test_missing_required_field_is_rejected(session):
    with pytest.raises(InvalidRequest):
        CreateGeneration(session).execute("a", "corte", {"instructions": "x"}, [Target("tiktok")])
