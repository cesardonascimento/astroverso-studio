from app.algorithms.base import Algorithm, InputField
from app.algorithms.corte.steps.check_cut import CheckCut
from app.algorithms.corte.steps.download_source import DownloadSource
from app.algorithms.corte.steps.plan_cut import PlanCut
from app.algorithms.corte.steps.render_cut import RenderCut
from app.algorithms.corte.steps.transcribe_source import TranscribeSource

CORTE = Algorithm(
    id="corte",
    name="Corte de vídeo",
    description="Escolhe o melhor trecho de um vídeo longo do YouTube e monta o corte vertical com legendas "
                "palavra por palavra.",
    fields=[InputField("url", "Link do YouTube", "url", required=True),
            InputField("instructions", "Instruções", "textarea",
                       help="Opcional. Ex.: foca na parte sobre dinheiro, máximo 40 segundos.")],
    preparation=[DownloadSource, TranscribeSource],
    planning=PlanCut,
    rendering=[RenderCut, CheckCut],
)
