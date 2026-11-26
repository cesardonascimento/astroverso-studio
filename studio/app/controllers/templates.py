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


def pop_flash(request) -> dict | None:
    return request.session.pop("flash", None)


templates.env.globals["pop_flash"] = pop_flash


def clock(seconds: float | None) -> str:
    if seconds is None:
        return ""
    minutes, rest = divmod(max(float(seconds), 0), 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours}:{minutes:02d}:{rest:04.1f}" if hours else f"{minutes}:{rest:04.1f}"


templates.env.filters["clock"] = clock
