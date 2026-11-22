"""Geração/obtenção de imagens por cena (1080x1920)."""
from __future__ import annotations

import hashlib
import io
import textwrap
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..config import settings
from ..db import record_generation

W, H = 1080, 1920


class ImageProvider:
    name = "base"

    def get(self, *, prompt: str, query: str, out: Path, ctx: dict | None = None) -> dict:  # pragma: no cover
        """Grava a imagem em `out` (jpg, 1080x1920) e devolve metadados (fonte, crédito...)."""
        raise NotImplementedError


def _fit(img: Image.Image) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), (W, H), Image.LANCZOS)


class PlaceholderImages(ImageProvider):
    """Cartões com gradiente + o prompt escrito. Só para validar o pipeline sem custo."""

    name = "placeholder"

    def get(self, *, prompt, query, out, ctx=None):
        h = hashlib.sha256(prompt.encode()).digest()
        c1, c2 = (h[0], h[1], h[2]), (h[3], h[4], h[5])
        img = Image.new("RGB", (W, H))
        px = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            px.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)))
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 44)
        except OSError:
            font = ImageFont.load_default()
        px.multiline_text((80, 300), textwrap.fill(query.upper(), 24), font=font, fill="white", spacing=12)
        img.save(out, "JPEG", quality=92)
        return {"source": "placeholder"}


class PexelsImages(ImageProvider):
    """Fotos do Pexels (API oficial e gratuita; licença permite uso comercial sem atribuição)."""

    name = "pexels"

    def get(self, *, prompt, query, out, ctx=None):
        key = settings().pexels_api_key
        if not key:
            raise RuntimeError("PEXELS_API_KEY não configurada no .env")
        t0 = time.monotonic()
        try:
            r = httpx.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "orientation": "portrait", "per_page": 5, "size": "large"},
                headers={"Authorization": key},
                timeout=30,
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos:
                raise RuntimeError(f"Pexels sem resultado para '{query}'")
            # escolhe de forma determinística (mesma cena → mesma foto em reprocessamentos)
            p = photos[int(hashlib.sha256(prompt.encode()).hexdigest(), 16) % len(photos)]
            data = httpx.get(p["src"]["large2x"], timeout=60).content
            _fit(Image.open(io.BytesIO(data))).save(out, "JPEG", quality=92)
        except Exception as e:
            record_generation(step="image", provider=self.name, units=1, cost_usd=0, ok=False,
                              duration_ms=int((time.monotonic() - t0) * 1000), error=repr(e)[:2000], **(ctx or {}))
            raise
        record_generation(step="image", provider=self.name, units=1, cost_usd=0, ok=True,
                          duration_ms=int((time.monotonic() - t0) * 1000), **(ctx or {}))
        return {"source": "pexels", "photo_id": p["id"], "photographer": p.get("photographer"), "url": p.get("url")}


def image_provider() -> ImageProvider:
    return {"placeholder": PlaceholderImages, "pexels": PexelsImages}[settings().image_provider]()
