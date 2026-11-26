from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.algorithms import ALGORITHMS
from app.config import settings
from app.controllers.database import database
from app.controllers.templates import templates
from app.services.catalog import ListNetworks, ListSubtitlePresets
from app.services.generations import BuildTargets, CreateGeneration, InvalidRequest

router = APIRouter()


def render_form(request: Request, error: str | None = None, values: dict | None = None, status_code: int = 200):
    return templates.TemplateResponse(request, "generations/new.html", {
        "algorithms": list(ALGORITHMS.values()), "networks": ListNetworks().execute(),
        "presets": ListSubtitlePresets().execute(), "error": error, "values": values or {}}, status_code=status_code)


@router.get("/generations/new", response_class=HTMLResponse)
def new(request: Request):
    return render_form(request)


@router.post("/generations")
async def create(request: Request, session: Session = Depends(database)):
    form = await request.form()
    data = {key: form.getlist(key) for key in form.keys()}
    algorithm = (data.get("algorithm") or [""])[0]
    inputs = {key.removeprefix("input."): values[0] for key, values in data.items() if key.startswith("input.")}
    try:
        generation = CreateGeneration(session).execute(settings().instance_name, algorithm, inputs,
                                                       BuildTargets().execute(data))
    except (InvalidRequest, LookupError) as error:
        session.rollback()
        return render_form(request, str(error), {key: values[0] for key, values in data.items()}, 422)
    return RedirectResponse(f"/generations/{generation.id}", status_code=303)
