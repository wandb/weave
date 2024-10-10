from weave.flow.scorer.base_scorer import Scorer

from typing import Union
import re
from pydantic import Field
import weave

class RegexScorer(Scorer):
    patterns: Union[str, list[str]] = Field(default_factory=list, description="The patterns or keywords to match")
    ignore_case: bool = True
    ignore_whitespace: bool = False
    use_regex: bool = False  # Use regex patterns if True
    match_full_string: bool = False  # Match the entire string if True
    target_column: str = Field(default="target", description="The class name to match")

    @weave.op
    def score(self, model_output: Union[dict, str], target: Union[str, list[str], None] = None) -> dict:
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
                pattern = ''.join(pattern.split())
            if self.match_full_string:
                pattern = f'^{pattern}$'
            compiled_patterns.append(re.compile(pattern, flags=flags))

        text_to_search = model_output.get("output") if model_output else ""
        if self.ignore_whitespace:
            text_to_search = ''.join(text_to_search.split())

        match_found = any(pattern.search(text_to_search) for pattern in compiled_patterns)

        return {"string_match": match_found}