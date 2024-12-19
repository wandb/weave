import pytest
from unittest.mock import MagicMock, patch

from weave.scorers.faithfulness_scorer import FaithfulnessScorer
from tests.scorers.test_utils import generate_large_text


@pytest.fixture
def faithfulness_scorer(monkeypatch):
    # Mock model loading
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    monkeypatch.setattr("transformers.AutoModelForSequenceClassification.from_pretrained", lambda *args, **kwargs: mock_model)
    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", lambda *args, **kwargs: mock_tokenizer)

    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    scorer = FaithfulnessScorer(
        model_name_or_path="wandb/faithfulness_scorer",
        device="cpu",
        name="test-faithfulness",
        description="Test faithfulness scorer",
        column_map={"output": "text", "context": "context"}
    )
    return scorer


@pytest.mark.asyncio
async def test_faithfulness_scorer_inheritance():
    from weave.scorers.hallucination_scorer import HallucinationScorer

    scorer = FaithfulnessScorer(
        model_name_or_path="wandb/faithfulness_scorer",
        device="cpu",
        name="test-faithfulness",
        description="Test faithfulness scorer",
        column_map={"output": "text", "context": "context"}
    )
    assert isinstance(scorer, HallucinationScorer)


@pytest.mark.asyncio
async def test_faithfulness_scorer_large_input(faithfulness_scorer):
    large_text = generate_large_text()
    context = "This is the context for testing."

    result = await faithfulness_scorer.score(large_text, context=context)

    assert isinstance(result, dict)
    assert "extras" in result
    assert "score" in result["extras"]
    assert isinstance(result["extras"]["score"], float)
    assert 0 <= result["extras"]["score"] <= 1


@pytest.mark.asyncio
async def test_faithfulness_scorer_error_handling(faithfulness_scorer):
    with pytest.raises(ValueError):
        await faithfulness_scorer.score("", context="Some context")
    with pytest.raises(ValueError):
        await faithfulness_scorer.score("Some response", context="")
