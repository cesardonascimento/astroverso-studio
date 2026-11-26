from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.controllers.database import database
from app.controllers.flash import redirect_with_flash
from app.controllers.templates import templates
from app.models import Generation, GenerationState
from app.services.catalog import ListSubtitlePresets
from app.services.generations import (CancelGeneration, DeleteOriginal, DescribeProgress, GetGeneration,
                                      ListGenerations, RetryGeneration)
from app.services.outputs import ActionNotAllowed

router = APIRouter()


def load(session: Session, generation_id: int) -> Generation:
    try:
        return GetGeneration(session).execute(generation_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/")
def home():
    return RedirectResponse("/generations", status_code=303)


@router.get("/generations", response_class=HTMLResponse)
def index(request: Request, state: str = "", instance: str = "", session: Session = Depends(database)):
    return templates.TemplateResponse(request, "generations/index.html", {
        "generations": ListGenerations(session).execute(state, instance), "state": state, "instance": instance})


@router.get("/generations/{generation_id}", response_class=HTMLResponse)
def show(request: Request, generation_id: int, session: Session = Depends(database)):
    generation = load(session, generation_id)
    return templates.TemplateResponse(request, "generations/show.html", {
        "generation": generation, "algorithm": get_algorithm(generation.algorithm), "progress": DescribeProgress(),
        "presets": ListSubtitlePresets().execute()})


@router.get("/generations/{generation_id}/preparation", response_class=HTMLResponse)
def preparation(request: Request, generation_id: int, session: Session = Depends(database)):
    generation = load(session, generation_id)
    if generation.state != GenerationState.PREPARING:
        return Response(headers={"HX-Refresh": "true"})
    return templates.TemplateResponse(request, "generations/_preparation.html",
                                      {"generation": generation, "progress": DescribeProgress()})


@router.get("/generations/{generation_id}/events", response_class=HTMLResponse)
def events(request: Request, generation_id: int, session: Session = Depends(database)):
    return templates.TemplateResponse(request, "generations/_events.html", {"generation": load(session, generation_id)})


@router.post("/generations/{generation_id}/cancel")
def cancel(request: Request, generation_id: int, session: Session = Depends(database)):
    CancelGeneration(session).execute(generation_id)
    return redirect_with_flash(request, f"/generations/{generation_id}", "Geração cancelada.")


@router.post("/generations/{generation_id}/retry")
def retry(request: Request, generation_id: int, session: Session = Depends(database)):
    try:
        RetryGeneration(session).execute(generation_id)
    except ActionNotAllowed as error:
        return redirect_with_flash(request, f"/generations/{generation_id}", str(error), "danger")
    return redirect_with_flash(request, f"/generations/{generation_id}", "Tentando de novo.")


@router.post("/generations/{generation_id}/delete-original")
def delete_original(request: Request, generation_id: int, session: Session = Depends(database)):
    try:
        DeleteOriginal(session).execute(generation_id)
    except ActionNotAllowed as error:
        return redirect_with_flash(request, f"/generations/{generation_id}", str(error), "danger")
    return redirect_with_flash(request, f"/generations/{generation_id}", "Vídeo original apagado.")
