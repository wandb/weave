import re
from typing import Union, List, Any

from pydantic import Field, model_validator

import weave
from weave.flow.scorer.base_scorer import Scorer

class StringScorer(Scorer):
    """
    Scorer that checks if the model output string is found in the search columns of the dataset row.
    """
    target_columns: List[str] = Field(default_factory=list, description="The names of the columns that are used as input to the scorer")

    def score(self, model_output: Any, dataset_row: dict) -> dict:
        string_in_input = any([model_output.lower() in input.lower() for k, input in dataset_row.items() if k in self.target_columns])
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
        self, model_output: Union[dict, str], target: Union[str, list[str], None] = None
    ) -> dict:
        if isinstance(model_output, str):
            model_output = {"output": model_output}

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

        text_to_search = model_output.get("output") if model_output else ""
        if self.ignore_whitespace:
            text_to_search = "".join(text_to_search.split())

        match_found = any(
            pattern.search(text_to_search) for pattern in compiled_patterns
        )

        return {"string_match": match_found}


class LevenshteinScorer(Scorer):
    @model_validator(mode='after')
    def check_levenshtein(self):
        try:
            from Levenshtein import distance
        except ImportError:
            raise ValueError("Levenshtein package not found. Please install it with `pip install Levenshtein`")

    @weave.op
    def score(self, model_output: str, target: str) -> dict:
        distance = distance(model_output, target)
        return {"levenshtein_distance": distance}


if __name__ == "__main__":
    import asyncio

    scorer = StringScorer(target_columns=["col1", "col2"])
    
    @weave.op
    def f(col1, col2): 
        return "Hello"    

    model_output = f(col1="hello", col2="world")
    dataset_row = {"col1": "Hello my name is Morgan", "col2": "I am an engineer"}
    print(scorer.score(model_output=model_output, dataset_row=dataset_row))

    dataset = [{"col1": "Hello my name is Morgan", "col2": "I am an engineer", "target": "Morgan"}, 
               {"col1": "Hello my name is John", "col2": "I am a doctor", "target": "John"}]
    
    evaluation = weave.Evaluation(dataset=dataset, scorers=[scorer])

    eval_out = asyncio.run(evaluation.evaluate(f))