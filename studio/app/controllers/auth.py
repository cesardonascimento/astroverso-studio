from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.controllers.templates import templates
from app.services.auth import CheckPassword

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/login")
def login(request: Request, password: str = Form("")):
    if not CheckPassword(settings().studio_password).execute(password):
        return templates.TemplateResponse(request, "auth/login.html", {"error": "Senha incorreta."}, status_code=401)
    request.session["logged_in"] = True
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
