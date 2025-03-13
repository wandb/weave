import verdict
import weave
from pydantic import Field
from typing import Dict
from weave import Scorer

class VerdictScorer(Scorer):
    """
    A scorer that executes a passed Verdict pipeline to score an input.

    Args:
        pipeline: The Verdict pipeline to use for scoring

    Note: This Scorer's `score` method will accept any number of keyword arguments. These can be referenced in the
    Verdict prompt using the `{source.KEY}` template variable. Moreover, this Scorer will return a dictionary with
    all Verdict leaf outputs indexed by their prefix (e.g., 'Pipeline_root.block.unit[DirectScoreJudge]_score'). To
    return custom keys, subclass this Scorer and override the `score` method.

    Returns:
        dict: A dictionary containing each Verdict leaf node identifier as a key and the node output as a value.

    Example:
        >>> pipeline = verdict.Pipeline() \
        ...     >> JudgeUnit(BooleanScale(), explanation=True).prompt('''
        ...         Is the <output> to the <query> consistent with the <context>?
        ...         <query>{source.query}</query>
        ...         <context>{source.context}</context>
        ...         <output>{source.output}</output>
        ...     ''')
        >>> scorer = VerdictScorer(pipeline)
        >>> result = scorer.score(
        ...     query="What is the capital of France?",
        ...     context="Paris is the capital of France.",
        ...     output="Paris."
        ... )
        >>> print(result)
        {
            'Pipeline_root.block.unit[DirectScoreJudge]_score': True,
            'Pipeline_root.block.unit[DirectScoreJudge]_explanation': 'The context specifically mentions that the capital of France is Paris.'
        }
    """

    pipeline: verdict.Pipeline = Field(description="The Verdict pipeline to use for judging")

    @weave.op
    def score(self, output: str, **kwargs: Dict[str, str]) -> dict:
        response, leaf_node_prefixes = self.pipeline.run(verdict.schema.Schema.of(output=output, **kwargs))
        return {prefix: response[prefix] for prefix in leaf_node_prefixes}
