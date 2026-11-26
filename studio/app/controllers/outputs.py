from fastapi import APIRouter, Depends, Form, HTTPException, Request
from urllib.parse import quote

from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.config import settings
from app.controllers.database import database
from app.controllers.flash import redirect_with_flash
from app.controllers.templates import templates
from app.models import Output, VersionKind
from app.services.catalog import ListSubtitlePresets
from app.services.generations import DescribeProgress
from app.services.outputs import (ActionNotAllowed, ApproveOutput, BuildVideoName, CancelOutput, OpenVideo, ReplanOutput,
                                 RerenderOutput, RetryOutput)

router = APIRouter()


def load(session: Session, output_id: int) -> Output:
    output = session.get(Output, output_id)
    if output is None:
        raise HTTPException(404, "saída não encontrada")
    return output


def back(request: Request, output: Output, message: str, kind: str = "success"):
    return redirect_with_flash(request, f"/generations/{output.generation_id}#output-{output.id}", message, kind)


@router.get("/outputs/{output_id}/card", response_class=HTMLResponse)
def card(request: Request, output_id: int, session: Session = Depends(database)):
    output = load(session, output_id)
    return templates.TemplateResponse(request, "generations/_output.html", {
        "output": output, "generation": output.generation,
        "algorithm": get_algorithm(output.generation.algorithm), "progress": DescribeProgress(),
        "presets": ListSubtitlePresets().execute()})


@router.post("/outputs/{output_id}/approve")
async def approve(request: Request, output_id: int, session: Session = Depends(database)):
    output = load(session, output_id)
    form = await request.form()
    try:
        ApproveOutput(session).execute(output_id, {key: form.getlist(key) for key in form.keys()})
    except ActionNotAllowed as error:
        session.rollback()
        return back(request, output, str(error), "danger")
    return back(request, output, "Roteiro aprovado. Renderizando.")


@router.post("/outputs/{output_id}/replan")
def replan(request: Request, output_id: int, text: str = Form(""), session: Session = Depends(database)):
    output = load(session, output_id)
    try:
        ReplanOutput(session).execute(output_id, text)
    except ActionNotAllowed as error:
        return back(request, output, str(error), "danger")
    return back(request, output, "Pedido enviado. Escrevendo um novo roteiro.")


@router.post("/outputs/{output_id}/cancel")
def cancel(request: Request, output_id: int, session: Session = Depends(database)):
    output = load(session, output_id)
    CancelOutput(session).execute(output_id)
    return back(request, output, "Saída cancelada.")


@router.post("/outputs/{output_id}/retry")
def retry(request: Request, output_id: int, session: Session = Depends(database)):
    output = load(session, output_id)
    try:
        RetryOutput(session).execute(output_id)
    except ActionNotAllowed as error:
        return back(request, output, str(error), "danger")
    return back(request, output, "Tentando de novo.")


@router.post("/outputs/{output_id}/revise")
def revise(request: Request, output_id: int, text: str = Form(""), session: Session = Depends(database)):
    output = load(session, output_id)
    try:
        ReplanOutput(session).execute(output_id, text, VersionKind.REVISION)
    except ActionNotAllowed as error:
        return back(request, output, str(error), "danger")
    return back(request, output, "Alteração enviada. O vídeo novo sai sem precisar de aprovação.")


@router.post("/outputs/{output_id}/rerender")
def rerender(request: Request, output_id: int, layout: str = Form("auto"), subtitle_preset: str = Form(""),
             session: Session = Depends(database)):
    output = load(session, output_id)
    try:
        RerenderOutput(session).execute(output_id, layout, subtitle_preset)
    except ActionNotAllowed as error:
        return back(request, output, str(error), "danger")
    return back(request, output, "Renderizando de novo.")


@router.get("/outputs/{output_id}/videos/{version}")
def video(request: Request, output_id: int, version: int, download: bool = False,
          session: Session = Depends(database)):
    try:
        opened = OpenVideo(session).execute(output_id, version, request.headers.get("range"))
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    stream = opened.stream
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(stream.content_length)}
    if stream.content_range:
        headers["Content-Range"] = stream.content_range
    if download:
        name = BuildVideoName(settings().tz).execute(opened.version) + ".mp4"
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
    return StreamingResponse(stream.chunks, status_code=206 if stream.content_range else 200,
                             media_type="video/mp4", headers=headers)
