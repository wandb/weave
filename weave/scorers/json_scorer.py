import json
from typing import Any

import weave
from weave.flow.scorer import Scorer
from weave.trace.objectify import register_object


@register_object
class ValidJSONScorer(Scorer):
    """Validate whether a string is valid JSON."""

    @weave.op
    def score(self, *, output: Any, **kwargs: Any) -> dict:
        try:
            _ = json.loads(output)
        except json.JSONDecodeError:
            return {"json_valid": False}
        else:
            return {"json_valid": True}
