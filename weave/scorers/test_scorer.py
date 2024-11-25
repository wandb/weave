import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.scorer_env import getenv


class TestScorer(Scorer):
    scorer_property: int
    builtin_scorer_id: str = "test_scorer"

    # TODO: I need a general purpose way to add context (like documents)
    # and/or labels.
    # TODO: I don't like that we have to know the names of the inputs!
    @weave.op
    def score(self, a: int, b: str, output: str) -> dict:
        test_api_key = getenv("TEST_API_KEY")
        return {
            "input_a": a,
            "input_b_length": len(b),
            "output_length": len(output),
            "scorer_property": self.scorer_property,
            "test_api_key_length": len(test_api_key) if test_api_key else None,
        }
