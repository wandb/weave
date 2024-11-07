from typing import Callable

from pydantic import Field, model_validator

import weave
from weave.scorers.base_scorer import Scorer


class StringMatchScorer(Scorer):
    """Scorer that checks if the model output string is found in the search columns of the dataset row."""

    @weave.op
    def score(self, output: str, target: str) -> dict:
        string_in_input = output.lower() in target.lower()
        return {"string_in_input": string_in_input}


class LevenshteinScorer(Scorer):
    distance: Callable[[str, str], int] = Field(
        default=None, description="The Levenshtein distance function"
    )

    @model_validator(mode="after")
    def check_levenshtein(self) -> "LevenshteinScorer":
        try:
            from Levenshtein import distance

            self.distance = distance
        except ImportError:
            raise ValueError(
                "Levenshtein package not found. Please install it with `pip install Levenshtein`"
            )
        else:
            return self

    @weave.op
    def score(self, output: str, target: str) -> dict:
        distance = self.distance(output, target)
        return {"levenshtein_distance": distance}
