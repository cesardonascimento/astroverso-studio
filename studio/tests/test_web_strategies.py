import shutil

import pytest

from app.config import CONTENT_DIR


@pytest.fixture
def content(monkeypatch, tmp_path):
    copy = tmp_path / "content"
    shutil.copytree(CONTENT_DIR, copy)
    for module in ("app.services.catalog.list_strategies", "app.services.catalog.list_networks",
                   "app.services.strategies.strategy_path"):
        monkeypatch.setattr(f"{module}.CONTENT_DIR", copy)
    return copy


def test_lists_strategies_by_network(client, content):
    page = client.get("/strategies").text
    assert "TikTok" in page and "viral" in page and "emotivo" in page


def test_create_edit_rename_and_delete(client, content):
    folder = content / "networks" / "tiktok" / "strategies"
    client.post("/strategies/tiktok", data={"name": "ASMR Calmo", "description": "sons suaves", "text": "## Ritmo\nlento"})
    assert "name: asmr-calmo" in (folder / "asmr-calmo.md").read_text()

    client.post("/strategies/tiktok", data={"name": "asmr", "description": "sons", "text": "x",
                                            "previous_name": "asmr-calmo"})
    assert (folder / "asmr.md").exists() and not (folder / "asmr-calmo.md").exists()

    client.post("/strategies/tiktok/asmr/delete")
    assert not (folder / "asmr.md").exists()


def test_duplicate_and_auto_names_are_refused(client, content):
    assert client.post("/strategies/tiktok", data={"name": "viral", "description": "d", "text": "t"}).status_code == 422
    assert client.post("/strategies/tiktok", data={"name": "auto", "description": "d", "text": "t"}).status_code == 422


def test_export_and_import_skill_md(client, content):
    exported = client.get("/strategies/tiktok/viral/export").text
    assert exported.startswith("---\nname: viral\ndescription:")
    imported = exported.replace("name: viral", "name: viral-2")
    client.post("/strategies/tiktok/import", files={"file": ("viral-2.md", imported, "text/markdown")})
    assert (content / "networks" / "tiktok" / "strategies" / "viral-2.md").exists()


def test_preview_escapes_html(client):
    html = client.post("/strategies/preview", data={"text": "## Título\n<script>x</script>"}).text
    assert "<h2>Título</h2>" in html and "<script>" not in html
