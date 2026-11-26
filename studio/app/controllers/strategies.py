from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.controllers.flash import redirect_with_flash
from app.controllers.templates import templates
from app.services.catalog import ListNetworks, Strategy
from app.services.strategies import (DeleteStrategy, ExportStrategy, GetStrategy, ImportStrategy, InvalidStrategy,
                                     RenderMarkdown, SaveStrategy)

router = APIRouter()


def editor(request: Request, network: str, strategy: Strategy | None, previous_name: str = "",
           error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(request, "strategies/edit.html", {
        "network": network, "strategy": strategy, "previous_name": previous_name, "error": error,
        "preview": RenderMarkdown().execute(strategy.text if strategy else "")}, status_code=status_code)


@router.get("/strategies", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "strategies/index.html", {"networks": ListNetworks().execute()})


@router.post("/strategies/preview", response_class=HTMLResponse)
def preview(text: str = Form("")):
    return HTMLResponse(RenderMarkdown().execute(text))


@router.get("/strategies/{network}/new", response_class=HTMLResponse)
def new(request: Request, network: str):
    return editor(request, network, None)


@router.get("/strategies/{network}/{name}", response_class=HTMLResponse)
def edit(request: Request, network: str, name: str):
    try:
        strategy = GetStrategy().execute(network, name)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    return editor(request, network, strategy, previous_name=name)


@router.post("/strategies/{network}")
def save(request: Request, network: str, name: str = Form(""), description: str = Form(""), text: str = Form(""),
         previous_name: str = Form("")):
    try:
        saved = SaveStrategy().execute(network, name, description, text, previous_name)
    except (InvalidStrategy, LookupError) as error:
        draft = Strategy(network=network, name=name, description=description, text=text)
        return editor(request, network, draft, previous_name, str(error), 422)
    return redirect_with_flash(request, "/strategies",
                               f"Estratégia {saved.name} salva em content/. Faça commit para guardar no git.")


@router.post("/strategies/{network}/{name}/delete")
def delete(request: Request, network: str, name: str):
    try:
        DeleteStrategy().execute(network, name)
    except InvalidStrategy as error:
        return redirect_with_flash(request, "/strategies", str(error), "danger")
    return redirect_with_flash(request, "/strategies", f"Estratégia {name} apagada.")


@router.get("/strategies/{network}/{name}/export")
def export(network: str, name: str):
    try:
        content = ExportStrategy().execute(network, name)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    return Response(content, media_type="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}.md"})


@router.post("/strategies/{network}/import")
async def import_file(request: Request, network: str, file: UploadFile):
    try:
        saved = ImportStrategy().execute(network, (await file.read()).decode("utf-8", errors="replace"))
    except (InvalidStrategy, LookupError) as error:
        return redirect_with_flash(request, "/strategies", str(error), "danger")
    return redirect_with_flash(request, "/strategies", f"Estratégia {saved.name} importada.")
