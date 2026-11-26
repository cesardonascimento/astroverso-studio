from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.algorithms import get_algorithm
from app.controllers.database import database
from app.controllers.flash import redirect_with_flash
from app.controllers.templates import templates
from app.models import Output
from app.services.generations import DescribeProgress
from app.services.outputs import ActionNotAllowed, ApproveOutput, CancelOutput, ReplanOutput, RetryOutput

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
        "algorithm": get_algorithm(output.generation.algorithm), "progress": DescribeProgress()})


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
