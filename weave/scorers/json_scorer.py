import json
from typing import Any

import weave
from weave.flow.scorer import Scorer


class ValidJSONScorer(Scorer):
    """Validate whether a string is valid JSON."""

    @weave.op
    def score(self, output: Any) -> dict:
        try:
            _ = json.loads(output)
        except json.JSONDecodeError:
            return {"json_valid": False}
        else:
            return {"json_valid": True}
