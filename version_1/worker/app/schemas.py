"""Formatos de saída do LLM (validados). Sem min/max numéricos: o structured outputs não aceita."""
from pydantic import BaseModel, Field


# ---------- Análise de tendências ----------
class Theme(BaseModel):
    theme: str = Field(description="nome curto do tema, em português")
    description: str = Field(description="o que está acontecendo e por que as pessoas se importam")
    related_hashtags: list[str]
    momentum: str = Field(description="rising | peaking | stable")
    content_angles: list[str] = Field(description="3-5 ângulos de vídeo que um canal faceless poderia explorar")
    fit_score: int = Field(description="0-10: quão bem dá para fazer vídeo narrado com imagens de IA/banco de imagens")
    risk_notes: str = Field(description="riscos: marca registrada, pessoa real, tragédia, política, saúde... ou vazio")


class TrendAnalysis(BaseModel):
    themes: list[Theme]
    skipped: list[str] = Field(description="hashtags ignoradas (ex.: só de anúncios, nomes próprios sem contexto) e o motivo")


# ---------- Ideias ----------
class IdeaScores(BaseModel):
    hook: int = Field(description="0-10 força do gancho nos primeiros 2 segundos")
    curiosity: int = Field(description="0-10 lacuna de curiosidade")
    retention: int = Field(description="0-10 potencial de a pessoa assistir até o fim")
    trend_fit: int = Field(description="0-10 conexão real com a tendência")
    originality: int = Field(description="0-10 não é o mesmo vídeo que todo mundo já fez")
    shareability: int = Field(description="0-10 vontade de mandar pra alguém")
    commentability: int = Field(description="0-10 provoca comentário/opinião")
    clarity: int = Field(description="0-10 dá para entender sem contexto")
    production_ease: int = Field(description="0-10 fácil de ilustrar com imagens genéricas/IA")
    risk_repetition: int = Field(description="0-10 risco de ser repetitivo/genérico (alto = ruim)")
    risk_content: int = Field(description="0-10 risco de violar diretrizes, desinformar ou expor pessoa real (alto = ruim)")


class Idea(BaseModel):
    theme: str = Field(description="tema de origem, exatamente como veio na lista")
    title: str
    hook: str = Field(description="frase falada/escrita nos primeiros 1-2 segundos")
    angle: str = Field(description="qual é a sacada / payoff do vídeo")
    format: str = Field(description="ex.: curiosidade, lista rápida, mito vs verdade, você sabia, antes/depois, POV")
    why_now: str = Field(description="por que esse vídeo aproveita a tendência agora")
    related_hashtags: list[str]
    target_duration_s: int
    scores: IdeaScores
    risk_notes: str


class IdeaBatch(BaseModel):
    ideas: list[Idea]


# ---------- Roteiro ----------
class Scene(BaseModel):
    narration: str = Field(description="texto falado nesta cena (pt-BR natural, frases curtas)")
    on_screen_text: str = Field(description="texto curto de apoio na tela, ou vazio")
    visual_prompt: str = Field(description="prompt de imagem EM INGLÊS, vertical 9:16, sem texto na imagem")
    stock_query: str = Field(description="2-4 palavras EM INGLÊS para buscar foto em banco de imagens")


class FactClaim(BaseModel):
    claim: str
    confidence: str = Field(description="high | medium | low")


class Script(BaseModel):
    title: str
    hook_text: str = Field(description="texto grande na tela no primeiro segundo (máx. ~7 palavras)")
    scenes: list[Scene] = Field(description="a primeira cena É o gancho. Troca visual a cada 2-4 segundos")
    loop_line: str = Field(description="última frase que conecta de volta com o início (ou vazio)")
    cta: str = Field(description="chamada curta e natural (ou vazio)")
    caption: str = Field(description="legenda do post, 1-2 linhas")
    hashtags: list[str] = Field(description="3-6 hashtags, misturando a tendência e o nicho")
    fact_claims: list[FactClaim] = Field(description="afirmações factuais do roteiro")


class ScriptReview(BaseModel):
    approved: bool
    hook_strength: int = Field(description="0-10")
    coherence: int = Field(description="0-10")
    factual_risk: int = Field(description="0-10 (alto = provável erro factual)")
    policy_risk: int = Field(description="0-10 (alto = provável violação de diretrizes do TikTok)")
    issues: list[str]
