import pytest

import weave
from tests.scorers.test_utils import TINY_MODEL_PATHS
from weave.scorers import LlamaGuardScorer
from weave.scorers.utils import download_model


@pytest.fixture
def llamaguard_scorer():
    model_path = download_model(TINY_MODEL_PATHS["llamaguard_scorer"])
    return LlamaGuardScorer(model_name_or_path=model_path)


def test_llamaguard_postprocess(llamaguard_scorer):
    # Test safe content
    safe_output = ("safe", 0.1)
    result = llamaguard_scorer.postprocess(*safe_output)
    assert result["safe"]
    assert result["extras"]["categories"] == {}
    assert result["extras"]["unsafe_score"] == 0.1

    # Test unsafe content with category
    unsafe_output = ("unsafe\nS5<|eot_id|>", 0.9)
    result = llamaguard_scorer.postprocess(*unsafe_output)
    assert not result["safe"]
    assert result["extras"]["categories"] == {"Defamation": True}
    assert result["extras"]["unsafe_score"] == 0.9


@pytest.mark.asyncio
async def test_llamaguard_score(llamaguard_scorer):
    output = "Test content for scoring"
    result = await llamaguard_scorer.score(output=output)
    assert isinstance(result, dict)
    assert "safe" in result
    assert "extras" in result
    assert "categories" in result["extras"]
    assert "unsafe_score" in result["extras"]
    assert result["safe"] is True
    assert result["extras"]["categories"] == {}


@pytest.mark.asyncio
async def test_llamaguard_evaluation(llamaguard_scorer):
    dataset = [
        {"input": "This is a unsafe text."},
        {"input": "This is also bad text"},
    ]

    @weave.op
    def model(input: str):
        return input

    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[llamaguard_scorer],
    )
    result = await evaluation.evaluate(model)
    assert result["LlamaGuardScorer"]["safe"]["true_count"] == 2
