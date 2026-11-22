from pydantic import BaseModel, Field


class Segment(BaseModel):
    start: float = Field(description="segundos (tempo da primeira linha do segmento)")
    end: float = Field(description="segundos (início da linha seguinte à última que entra)")
    purpose: str = Field(description="papel no corte: gancho, contexto, desenvolvimento, payoff...")


class Alternative(BaseModel):
    start: float
    end: float
    summary: str


class Edit(BaseModel):
    type: str = Field(description="um dos efeitos disponíveis (lista no prompt). Nunca invente tipos.")
    start: float = Field(description="segundos no vídeo ORIGINAL")
    end: float = Field(description="segundos no vídeo ORIGINAL")
    params: str = Field(description='parâmetros do efeito em JSON, ex.: {"scale": 1.2}. Use "{}" se não houver')
    reason: str


class RenderSettings(BaseModel):
    layout: str = Field(description='"" para manter; ou auto | crop | fit_blur | split')
    subtitle_preset: str = Field(description='"" para manter; ou o nome de um preset de legenda da lista')
    crop_x: float = Field(description="-1 para manter; ou 0 (esquerda) a 1 (direita), só no layout crop")


class ClipPlan(BaseModel):
    title: str = Field(description="título interno do corte")
    hook_text: str
    segments: list[Segment]
    caption: str
    hashtags: list[str]
    why: str
    alternatives: list[Alternative]
    edits: list[Edit] = Field(description="efeitos de edição; lista vazia se não houver efeitos disponíveis")
    render: RenderSettings
    changes: str = Field(description="numa revisão: o que você mudou em relação à versão anterior; senão vazio")
