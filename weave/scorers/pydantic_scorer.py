from typing import Any

from pydantic import BaseModel, ValidationError

import weave


class PydanticScorer(weave.Scorer):
    """Validate the model output against a pydantic model."""

    model: type[BaseModel]

    @weave.op
    def score(self, *, output: Any, **kwargs: Any) -> dict:
        if isinstance(output, str):
            try:
                self.model.model_validate_json(output)
            except ValidationError:
                return {"valid_pydantic": False}
            else:
                return {"valid_pydantic": True}
        else:
            try:
                self.model.model_validate(output)
            except ValidationError:
                return {"valid_pydantic": False}
            else:
                return {"valid_pydantic": True}
