from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.controllers.database import database
from app.controllers.templates import templates
from app.services.generations import ListGenerations

router = APIRouter()


@router.get("/")
def home():
    return RedirectResponse("/generations", status_code=303)


@router.get("/generations", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(database)):
    return templates.TemplateResponse(request, "generations/index.html",
                                      {"generations": ListGenerations(session).execute()})
