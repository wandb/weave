from typing import Any

from pydantic import BaseModel, Field, ValidationError

import weave
from weave.scorers.base_scorer import Scorer


class PydanticScorerOutput(BaseModel):
    valid_pydantic: bool = Field(
        description="Whether the model output is valid against the pydantic model"
    )


class PydanticScorer(Scorer):
    """Validate the model output against a pydantic model."""

    model: type[BaseModel]

    @weave.op
    def score(self, output: Any) -> dict:
        if isinstance(output, str):
            try:
                self.model.model_validate_json(output)
            except ValidationError:
                return PydanticScorerOutput(valid_pydantic=False)
            else:
                return PydanticScorerOutput(valid_pydantic=True)
        else:
            try:
                self.model.model_validate(output)
            except ValidationError:
                return PydanticScorerOutput(valid_pydantic=False)
            else:
                return PydanticScorerOutput(valid_pydantic=True)
