import json
from typing import Any

from weave.flow.scorer.base_scorer import Scorer


class JSONScorer(Scorer):
    """Score a JSON string."""

    def score(self, output: Any, **kwargs: Any) -> dict:  # type: ignore
        try:
            result = json.loads(output)

            if isinstance(result, dict) or isinstance(result, list):
                return {"json_valid": True}

        except json.JSONDecodeError:
            pass
        return {"json_valid": False}
