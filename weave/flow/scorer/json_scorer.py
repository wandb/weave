import json
from typing import Any

from weave.flow.scorer.base_scorer import Scorer

class JSONScorer(Scorer):
    """
    Score a JSON string.
    """
    def score(self, model_output: Any) -> Any:
        try:
            result = json.loads(model_output)

            if isinstance(result, dict) or isinstance(result, list):
                return True

        except json.JSONDecodeError:
            pass
        return False
    

if __name__ == "__main__":
    scorer = JSONScorer()
    print(scorer.score("{\"city\": \"San Francisco\", \"country\": \"USA\", \"column2\": \"Santiago\"}"))