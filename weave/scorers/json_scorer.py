import json
from typing import Any

from pydantic import BaseModel, Field

import weave
from weave.scorers.base_scorer import Scorer


class ValidJSONScorerOutput(BaseModel):
    json_valid: bool = Field(description="Whether the model output is valid JSON")


class ValidJSONScorer(Scorer):
    """Validate whether a string is valid JSON."""

    @weave.op
    def score(self, output: Any) -> dict:
        try:
            _ = json.loads(output)
        except json.JSONDecodeError:
            return ValidJSONScorerOutput(json_valid=False)
        else:
            return ValidJSONScorerOutput(json_valid=True)
