from itertools import groupby

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.controllers.templates import templates
from app.dependencies import webdav_connection
from app.lib.webdav import CheckWebdavConnection
from app.services.settings import DescribeSettings

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
def index(request: Request):
    rows = DescribeSettings().execute()
    groups = [(group, list(items)) for group, items in groupby(rows, key=lambda row: row.group)]
    return templates.TemplateResponse(request, "settings/index.html", {"groups": groups,
                                                                       "webdav": webdav_connection() is not None})


@router.post("/settings/webdav-test", response_class=HTMLResponse)
def webdav_test(request: Request):
    connection = webdav_connection()
    problem = CheckWebdavConnection(connection).execute() if connection else "WebDAV desligado (WEBDAV_URL vazio)"
    return templates.TemplateResponse(request, "settings/_webdav_test.html", {"problem": problem})
