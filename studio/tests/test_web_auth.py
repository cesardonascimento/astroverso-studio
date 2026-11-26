from fastapi.testclient import TestClient

from app.main import app
from app.models import Generation


def test_pages_require_login():
    response = TestClient(app).get("/generations", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/login"


def test_htmx_requests_are_redirected_by_header():
    response = TestClient(app).get("/generations", headers={"HX-Request": "true"}, follow_redirects=False)
    assert response.status_code == 401 and response.headers["HX-Redirect"] == "/login"


def test_wrong_password_is_rejected():
    response = TestClient(app).post("/login", data={"password": "errada"})
    assert response.status_code == 401 and "Senha incorreta" in response.text


def test_logged_user_sees_generations(client, session):
    session.add(Generation(instance="a", algorithm="corte", inputs={"url": "x"}, title="Meu vídeo"))
    session.commit()
    response = client.get("/generations")
    assert response.status_code == 200 and "Meu vídeo" in response.text


def test_static_files_are_public():
    assert TestClient(app).get("/static/vendor/htmx/htmx.min.js").status_code == 200
