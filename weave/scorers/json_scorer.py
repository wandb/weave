import json
from typing import Any

import weave
from weave.scorers.base_scorer import Scorer


class ValidJSONScorer(Scorer):
    """Validate whether a string is valid JSON."""

    @weave.op
    def score(self, output: Any) -> dict:
        try:
            _ = json.loads(output)
            return {"json_valid": True}
        except json.JSONDecodeError:
            return {"json_valid": False}
