from app.algorithms.base import Step, StepContext
from app.services.exports import EXPORT_STEP, ExportVersion


class ExportStep(Step):
    name = EXPORT_STEP
    label = "Envio WebDAV"

    def execute(self, context: StepContext) -> str:
        return ExportVersion(context.session, context.workspace).execute(context.output)
