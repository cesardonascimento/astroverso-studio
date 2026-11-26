from fastapi import Request
from fastapi.responses import RedirectResponse


def redirect_with_flash(request: Request, url: str, message: str, kind: str = "success") -> RedirectResponse:
    request.session["flash"] = {"kind": kind, "message": message}
    return RedirectResponse(url, status_code=303)
