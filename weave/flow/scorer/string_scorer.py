import re
from typing import Union, Callable

from pydantic import Field, model_validator

import weave
from weave.flow.scorer.base_scorer import Scorer

class StringMatchScorer(Scorer):
    """
    Scorer that checks if the model output string is found in the search columns of the dataset row.
    """
    def score(self, output: str, target: str) -> dict:
        string_in_input = output.lower() in target.lower()
        return {"string_in_input": string_in_input}

class RegexScorer(Scorer):
    patterns: Union[str, list[str]] = Field(
        default_factory=list, description="The patterns or keywords to match"
    )
    ignore_case: bool = True
    ignore_whitespace: bool = False
    match_full_string: bool = False  # Match the entire string if True
    target_column: str = Field(default="target", description="The class name to match")

    @weave.op
    def score(
        self, output: Union[dict, str], target: Union[str, list[str], None] = None
    ) -> dict:
        if isinstance(output, str):
            output = {"output": output}

        # Use target patterns if provided
        patterns = target if target else self.patterns
        if isinstance(patterns, str):
            patterns = [patterns]

        flags = re.IGNORECASE if self.ignore_case else 0
        compiled_patterns = []
        for pattern in patterns:
            if not self.use_regex:
                pattern = re.escape(pattern)
            if self.ignore_whitespace:
                pattern = "".join(pattern.split())
            if self.match_full_string:
                pattern = f"^{pattern}$"
            compiled_patterns.append(re.compile(pattern, flags=flags))

        text_to_search = output.get("output") if output else ""
        if self.ignore_whitespace:
            text_to_search = "".join(text_to_search.split())

        match_found = any(
            pattern.search(text_to_search) for pattern in compiled_patterns
        )

        return {"string_match": match_found}


class LevenshteinScorer(Scorer):
    distance: Callable[[str, str], int] = Field(default=None, description="The Levenshtein distance function")
    @model_validator(mode='after')
    def check_levenshtein(self):
        try:
            from Levenshtein import distance
            self.distance = distance
        except ImportError:
            raise ValueError("Levenshtein package not found. Please install it with `pip install Levenshtein`")

    @weave.op
    def score(self, output: str, target: str) -> dict:
        distance = self.distance(output, target)
        return {"levenshtein_distance": distance}


if __name__ == "__main__":
    import asyncio

    match_scorer = StringMatchScorer(column_map={"output": "col1"})
    levenshtein_scorer = LevenshteinScorer(column_map={"output": "col2"})

    
    @weave.op
    def f(col1, col2): 
        return "Hello"    

    dataset = [{"col1": "Hello my name is Morgan", "col2": "I am an engineer", "target": "Morgan"}, 
               {"col1": "Hello my name is John", "col2": "I am a doctor", "target": "John"}]
    
    evaluation = weave.Evaluation(dataset=dataset, scorers=[match_scorer, levenshtein_scorer])

    eval_out = asyncio.run(evaluation.evaluate(f))