import re
from zoneinfo import ZoneInfo

from app.models import OutputVersion


class BuildVideoName:
    def __init__(self, timezone: str):
        self.timezone = ZoneInfo(timezone)

    def execute(self, version: OutputVersion) -> str:
        stamp = version.created_at.astimezone(self.timezone).strftime("%Y%m%d%H%M")
        title = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", version.plan.get("title") or "corte")
        return f"{stamp} - {re.sub(r' +', ' ', title).strip()[:120]}"
