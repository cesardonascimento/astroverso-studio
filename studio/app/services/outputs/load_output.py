from sqlalchemy.orm import Session

from app.models import Output


class LoadOutput:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, output_id: int) -> Output:
        output = self.session.get(Output, output_id, with_for_update=True)
        if output is None:
            raise LookupError(f"saída {output_id} não encontrada")
        return output
