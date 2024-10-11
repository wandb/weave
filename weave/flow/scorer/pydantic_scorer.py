from typing import Any, Type

from pydantic import BaseModel, ValidationError

from weave.flow.scorer.base_scorer import Scorer


class PydanticScorer(Scorer):
    """Validate the model output against a pydantic model."""

    model: Type[BaseModel]

    def score(self, output: Any):
        if isinstance(output, str):
            try:
                self.model.model_validate_json(output)
                return True
            except ValidationError:
                return False
        else:
            try:
                self.model.model_validate(output)
                return True
            except ValidationError:
                return False


if __name__ == "__main__":
    from pydantic import BaseModel

    class User(BaseModel):
        name: str
        age: int

    scorer = PydanticScorer(model=User)

    output = '{"name": "John", "age": 30}'
    print(scorer.score(output))

    output = {"name": "John", "age": 30}
    print(scorer.score(output))
