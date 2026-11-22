"""Score de ideias: explicável e fácil de ajustar.

O LLM dá notas 0-10 por critério. O código combina (o LLM não decide a nota final):

  base       = 10 * Σ(peso_i * nota_i)          → 0..100
  penalidade = 2*risk_repetition + 3*risk_content + 60*max(0, similaridade - 0.35)
  final      = base - penalidade

Corte automático: risk_content >= 7  ou  similaridade >= 0.6  → auto_rejected.
Quando houver métricas reais, estes pesos passam a ser recalibrados com os dados (etapa de feedback).
"""
from __future__ import annotations

WEIGHTS = {
    "hook": 0.20,
    "curiosity": 0.15,
    "retention": 0.15,
    "trend_fit": 0.15,
    "originality": 0.10,
    "shareability": 0.10,
    "commentability": 0.05,
    "clarity": 0.05,
    "production_ease": 0.05,
}
SIMILARITY_FREE = 0.35
AUTO_REJECT_RISK = 7
AUTO_REJECT_SIMILARITY = 0.6


def score_idea(scores: dict[str, int], similarity: float) -> tuple[float, dict, bool]:
    clamp = lambda v: max(0, min(10, int(v)))  # noqa: E731
    base = 10 * sum(w * clamp(scores.get(k, 0)) for k, w in WEIGHTS.items())
    pen_rep = 2 * clamp(scores.get("risk_repetition", 0))
    pen_risk = 3 * clamp(scores.get("risk_content", 0))
    pen_sim = 60 * max(0.0, similarity - SIMILARITY_FREE)
    final = round(base - pen_rep - pen_risk - pen_sim, 2)
    rejected = clamp(scores.get("risk_content", 0)) >= AUTO_REJECT_RISK or similarity >= AUTO_REJECT_SIMILARITY
    breakdown = {
        "base": round(base, 2),
        "penalty_repetition": pen_rep,
        "penalty_content_risk": pen_risk,
        "penalty_similarity": round(pen_sim, 2),
        "weights": WEIGHTS,
    }
    return final, breakdown, rejected
