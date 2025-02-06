from typing import Any

from pydantic import Field

import weave


class RougeScorer(weave.Scorer):
    rouge_scorer: Any = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        try:
            from rouge import Rouge

            self.rouge_scorer = Rouge()
        except ImportError:
            raise ImportError(
                "`rouge` is not installed. Please install it with `pip install rouge`"
            )

    @weave.op()
    def score(self, ground_truth: str, output: str) -> dict:
        assert (
            ground_truth is not None and output is not None
        ), "`ground_truth` and `output` cannot be None"

        # Handle empty strings
        if ground_truth == "" or output == "":
            return {
                "rouge-1": 0.0,
                "rouge-2": 0.0,
                "rouge-l": 0.0,
            }

        scores = self.rouge_scorer.get_scores(ground_truth, output)[0]
        return {
            "rouge-1": scores["rouge-1"]["f"],
            "rouge-2": scores["rouge-2"]["f"],
            "rouge-l": scores["rouge-l"]["f"],
        }
