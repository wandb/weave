import json
from typing import Any
from weave.trace.objectify import register_object
from weave.flow.scorer import BuiltInScorer
import weave

@register_object
class ValidJSONScorer(BuiltInScorer):
    """Validate whether a string is valid JSON."""

    @weave.op
    def score(self, output: Any) -> dict:
        try:
            _ = json.loads(output)
        except json.JSONDecodeError:
            return {"json_valid": False}
        else:
            return {"json_valid": True}
