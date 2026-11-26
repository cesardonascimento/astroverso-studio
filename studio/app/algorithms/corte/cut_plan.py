from pydantic import BaseModel, Field


class PlannedSegment(BaseModel):
    start: float = Field(description="segundos: tempo da primeira linha do segmento")
    end: float = Field(description="segundos: início da linha seguinte à última que entra")
    purpose: str = Field(description="papel no corte: gancho, contexto, desenvolvimento, payoff...")


class Alternative(BaseModel):
    start: float
    end: float
    summary: str


class RenderChoice(BaseModel):
    layout: str = Field(description='"" para manter; ou auto | crop | fit_blur | split')
    subtitle_preset: str = Field(description='"" para manter; ou o nome de um preset de legenda da lista')
    crop_x: float = Field(description="-1 para manter; ou 0 (esquerda) a 1 (direita), só no layout crop")


class CutPlan(BaseModel):
    strategy: str = Field(description="nome exato da estratégia seguida")
    title: str = Field(description="título interno curto do corte")
    hook_text: str
    segments: list[PlannedSegment]
    caption: str
    hashtags: list[str]
    why: str
    alternatives: list[Alternative]
    render: RenderChoice
    changes: str = Field(description="numa revisão: o que mudou em relação à versão anterior; senão vazio")
