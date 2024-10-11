from typing import Any, Type

from pydantic import BaseModel, ValidationError

from weave.flow.scorer.base_scorer import Scorer


class PydanticScorer(Scorer):
    """Validate the model output against a pydantic model."""

    model: Type[BaseModel]

    def score(self, output: Any) -> dict:  # type: ignore
        if isinstance(output, str):
            try:
                self.model.model_validate_json(output)
                return {"valid_pydantic": True}
            except ValidationError:
                return {"valid_pydantic": False}
        else:
            try:
                self.model.model_validate(output)
                return {"valid_pydantic": True}
            except ValidationError:
                return {"valid_pydantic": False}
