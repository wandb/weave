import json
from typing import Any

from weave.scorers.base_scorer import Scorer


class ValidJSONScorer(Scorer):
    """Validate whether a string is valid JSON."""

    def score(self, output: Any) -> dict:  # type: ignore
        try:
            _ = json.loads(output)
            return {"json_valid": True}
        except json.JSONDecodeError:
            return {"json_valid": False}
