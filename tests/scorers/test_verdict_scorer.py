import pytest

from weave.scorers.verdict_scorer import VerdictScorer

from verdict import Pipeline, Layer
from verdict.common.judge import JudgeUnit
from verdict.scale import BooleanScale
from verdict.transform import MaxPoolUnit


@pytest.fixture
def verdict_scorer() -> VerdictScorer:
    """Fixture to return a VerdictScorer instance with a 3x Verdict BooleanScale judge + MaxVote."""
    pipeline = Pipeline() \
        >> Layer(
            JudgeUnit(BooleanScale(), explanation=True).prompt("""
                Is the <output> to the <query> consistent with the <context>?
                <query>{source.query}</query>
                <context>{source.context}</context>
                <output>{source.output}</output>
            """)
        , repeat=3) \
        >> MaxPoolUnit()

    return VerdictScorer(pipeline)


def test_verdict_scorer_score(verdict_scorer):
    """Test score with a consistent output."""

    result = verdict_scorer.score(
        query="What is the capital of France?",
        context="Paris is the capital of France.",
        output="Paris."
    )

    assert result is not None
    assert result["Pipeline_root.block.block.unit[Map MaxPool]_score"] == True
