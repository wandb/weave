import json
from typing import Any

from weave.flow.scorers.base_scorer import Scorer


class ValidJSONScorer(Scorer):
    """Validate whether a string is valid JSON."""

    def score(self, output: Any) -> dict:  # type: ignore
        try:
            result = json.loads(output)

            if isinstance(result, dict) or isinstance(result, list):
                return {"json_valid": True}

        except json.JSONDecodeError:
            pass
        return {"json_valid": False}
