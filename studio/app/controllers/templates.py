from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from app.config import APP_DIR, settings

templates = Jinja2Templates(directory=APP_DIR / "views")


def local_time(value: datetime | None, pattern: str = "%d/%m %H:%M") -> str:
    if value is None:
        return ""
    return value.astimezone(ZoneInfo(settings().tz)).strftime(pattern)


templates.env.filters["local_time"] = local_time
templates.env.globals["instance_name"] = lambda: settings().instance_name
