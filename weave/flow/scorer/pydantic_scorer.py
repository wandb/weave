from pydantic import BaseModel, ValidationError
from typing import Any, Type

from weave.flow.scorer.base_scorer import Scorer

class PydanticScorer(Scorer):
    """
    Validate the model output against a pydantic model.
    """
    model: Type[BaseModel]

    def score(self, model_output: Any):
        if isinstance(model_output, str):
            try:
                self.model.model_validate_json(model_output)
                return True
            except ValidationError:
                return False
        else:
            try:
                self.model.model_validate(model_output)
                return True
            except ValidationError:
                return False


if __name__ == "__main__":
    from pydantic import BaseModel

    class User(BaseModel):
        name: str
        age: int

    scorer = PydanticScorer(model=User)

    model_output = "{\"name\": \"John\", \"age\": 30}"
    print(scorer.score(model_output))

    model_output = {"name": "John", "age": 30}
    print(scorer.score(model_output))
