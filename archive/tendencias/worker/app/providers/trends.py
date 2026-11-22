"""Fontes de tendências. Cada fonte devolve uma lista normalizada de TrendItem.

- apify: Creative Center do TikTok via scraper no Apify (NÃO é API oficial do TikTok;
  pode quebrar se o TikTok mudar o site). Hashtags por país (BR) + vídeos de referência (só US/JP/VN/TH/ID).
- manual: arquivo config/manual_trends.json — para testar sem custo ou complementar.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from ..config import settings
from ..db import record_generation

log = logging.getLogger(__name__)


@dataclass
class TrendItem:
    kind: str  # hashtag | video | sound | topic
    name: str
    rank: int | None = None
    posts: int | None = None
    views: int | None = None
    direction: str | None = None
    industries: list[str] = field(default_factory=list)
    country: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrendFetch:
    source: str
    country: str
    period_days: int
    items: list[TrendItem]
    raw: Any


class TrendSource:
    name = "base"

    def fetch(self, country: str, period_days: int) -> TrendFetch:  # pragma: no cover
        raise NotImplementedError


class ManualTrends(TrendSource):
    name = "manual"

    def fetch(self, country: str, period_days: int) -> TrendFetch:
        cfg = settings().config_dir
        path = cfg / "manual_trends.json"
        if not path.exists():
            path = cfg / "manual_trends.example.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = [TrendItem(**it) for it in raw["items"]]
        return TrendFetch(f"manual:{path.name}", country, period_days, items, raw)


class ApifyCreativeCenter(TrendSource):
    name = "apify"
    BASE = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

    def _run(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        s = settings()
        if not s.apify_token:
            raise RuntimeError("APIFY_TOKEN não configurado no .env")
        url = self.BASE.format(actor=s.apify_trend_actor)
        t0 = time.monotonic()
        try:
            r = httpx.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {s.apify_token}"},  # token fora da URL/logs
                timeout=300,
            )
            r.raise_for_status()
            rows = r.json()
        except Exception as e:
            record_generation(step="trend_fetch", provider="apify", model=s.apify_trend_actor,
                              duration_ms=int((time.monotonic() - t0) * 1000), ok=False, error=repr(e)[:2000])
            raise
        record_generation(step="trend_fetch", provider="apify", model=s.apify_trend_actor, units=len(rows),
                          # preço aproximado do actor: ~US$0,50-2/1000 resultados + taxa de início
                          cost_usd=round(0.005 + len(rows) * 0.002, 5),
                          duration_ms=int((time.monotonic() - t0) * 1000), ok=True)
        return rows

    def fetch(self, country: str, period_days: int) -> TrendFetch:
        hashtags = self._run({
            "trendType": "hashtags",
            "countryCode": country,
            "hashtagPeriod": str(period_days),
            "maxItems": 50,
        })
        items = [
            TrendItem(
                kind="hashtag",
                name=h.get("Hashtag", "").lstrip("#"),
                rank=h.get("Rank"),
                posts=h.get("Posts"),
                views=h.get("Video Views"),
                direction=h.get("Trend Direction"),
                industries=h.get("Industries") or [],
                country=h.get("Country Code"),
                data={"trend_stats": h.get("Trend Stats"), "url": h.get("TikTok URL")},
            )
            for h in hashtags if h.get("Hashtag")
        ]
        # vídeos em alta: o Creative Center só oferece alguns países (não BR).
        # Usamos US como referência de FORMATO, não de assunto.
        videos: list[dict[str, Any]] = []
        try:
            videos = self._run({
                "trendType": "videos", "videoCountry": "US", "videoPeriod": "7",
                "videoOrderBy": "2", "videoOrganicOnly": True, "maxItems": 15,
            })
        except Exception:  # noqa: BLE001 — referência opcional
            log.warning("falha ao buscar vídeos de referência; seguindo só com hashtags", exc_info=True)
        for v in videos:
            if v.get("Title"):
                items.append(TrendItem(
                    kind="video", name=v["Title"][:300], rank=v.get("Video Rank"), views=v.get("Views"),
                    industries=v.get("Content Tags") or [], country="US",
                    data={"url": v.get("Video TikTok URL"), "metrics": v.get("Metrics")},
                ))
        return TrendFetch(f"apify:{settings().apify_trend_actor}", country, period_days, items,
                          {"hashtags": hashtags, "videos": videos})


def trend_source() -> TrendSource:
    name = settings().trend_provider
    return {"manual": ManualTrends, "apify": ApifyCreativeCenter}[name]()
