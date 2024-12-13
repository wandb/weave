from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import torch
from torch import Tensor

from weave.scorers.moderation_scorer import RollingWindowScorer, ToxicityScorer, BiasScorer
from tests.scorers.test_utils import generate_large_text


# Define a concrete subclass for testing since RollingWindowScorer is abstract
class TestRollingWindowScorer(RollingWindowScorer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tokenizer = MagicMock()
        self._tokenizer.return_value = MagicMock(input_ids=torch.tensor([[1, 2, 3]]))
        self.device = "cpu"
        self._model = MagicMock()
        self._model.return_value = [0, 1]  # Default prediction values

    def model_post_init(self, __context: Any) -> None:
        """Mock implementation for testing."""
        pass

    def predict_chunk(self, input_ids: Tensor) -> list[int]:
        """Mock predict_chunk implementation."""
        return self._model(input_ids)

    def tokenize_input(self, text: str) -> Tensor:
        """Mock tokenize_input implementation."""
        if not hasattr(self, '_tokenizer'):
            self._tokenizer = MagicMock()
            self._tokenizer.return_value = MagicMock(input_ids=torch.tensor([[1, 2, 3]]))
        result = self._tokenizer(text, return_tensors="pt", truncation=False)
        return result.input_ids.to(self.device)

    async def score(self, output: str) -> dict[str, Any]:
        """Mock score method for testing."""
        return {"score": 0.5, "extras": {"category": "test"}}


@pytest.fixture
def scorer():
    scorer_instance = TestRollingWindowScorer()
    scorer_instance.model_post_init(None)
    return scorer_instance


@pytest.mark.asyncio
async def test_tokenize_input(scorer):
    prompt = "Test input for tokenizer."
    expected_tensor = Tensor([[1, 2, 3]])

    # Configure the tokenizer mock
    scorer._tokenizer.return_value = MagicMock(input_ids=expected_tensor)

    result = scorer.tokenize_input(prompt)

    # Assert tokenizer was called correctly
    scorer._tokenizer.assert_called_with(prompt, return_tensors="pt", truncation=False)
    # Assert the tokenized input is as expected
    assert torch.equal(result, expected_tensor.to(scorer.device))


@pytest.mark.asyncio
async def test_aggregate_predictions_max(scorer):
    scorer.aggregation_method = "max"
    all_predictions = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    expected = [7, 8, 9]
    result = scorer.aggregate_predictions(all_predictions)
    assert result == expected


@pytest.mark.asyncio
async def test_aggregate_predictions_average(scorer):
    scorer.aggregation_method = "average"
    all_predictions = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    expected = [4.0, 5.0, 6.0]
    result = scorer.aggregate_predictions(all_predictions)
    assert result == expected


@pytest.mark.asyncio
async def test_aggregate_predictions_invalid_method(scorer):
    scorer.aggregation_method = "invalid_method"
    all_predictions = [[1, 2], [3, 4]]
    with pytest.raises(ValueError) as exc_info:
        scorer.aggregate_predictions(all_predictions)
    assert "Unsupported aggregation method" in str(exc_info.value)


@pytest.mark.asyncio
async def test_predict_long_within_limit(scorer):
    prompt = "Short input."
    input_ids = Tensor([[1, 2, 3]])
    scorer._model.return_value = [0, 1]  # Set expected prediction values

    with patch.object(scorer, "tokenize_input", return_value=input_ids):
        predictions = scorer.predict(prompt)
        assert predictions == [0, 1], "Predictions should match mock values"


@pytest.mark.asyncio
async def test_tokenize_input_without_truncation(scorer):
    prompt = "Another test input."
    expected_tensor = Tensor([[4, 5, 6, 7]])

    # Configure the tokenizer mock
    scorer._tokenizer.return_value = MagicMock(input_ids=expected_tensor)

    result = scorer.tokenize_input(prompt)

    # Assert tokenizer was called without truncation
    scorer._tokenizer.assert_called_with(prompt, return_tensors="pt", truncation=False)
    # Assert the tokenized input is as expected
    assert torch.equal(result, expected_tensor.to(scorer.device))


@pytest.fixture
def toxicity_scorer(monkeypatch):
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    scorer = ToxicityScorer(
        model_name_or_path="wandb/toxicity_scorer",
        device="cpu",
        name="test-toxicity",
        description="Test toxicity scorer",
        column_map={"output": "text"}
    )
    monkeypatch.setattr(scorer, "_model", MagicMock())
    monkeypatch.setattr(scorer, "_tokenizer", MagicMock())
    return scorer


@pytest.fixture
def bias_scorer(monkeypatch):
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    scorer = BiasScorer(
        model_name_or_path="wandb/bias_scorer",
        device="cpu",
        name="test-bias",
        description="Test bias scorer",
        column_map={"output": "text"}
    )
    monkeypatch.setattr(scorer, "_model", MagicMock())
    monkeypatch.setattr(scorer, "_tokenizer", MagicMock())
    return scorer


@pytest.mark.asyncio
async def test_toxicity_scorer_large_input(toxicity_scorer):
    large_text = generate_large_text()

    result = await toxicity_scorer.score(large_text)

    assert "extras" in result
    assert all(cat in result["extras"] for cat in [
        "Race/Origin", "Gender/Sex", "Religion", "Ability", "Violence"
    ])


@pytest.mark.asyncio
async def test_bias_scorer_large_input(bias_scorer):
    large_text = generate_large_text()

    result = await bias_scorer.score(large_text)

    assert "extras" in result
    assert all(cat in result["extras"] for cat in ["gender_bias", "racial_bias"])


@pytest.mark.asyncio
async def test_toxicity_scorer_error_handling(toxicity_scorer):
    with pytest.raises(ValueError):
        await toxicity_scorer.score("")


@pytest.mark.asyncio
async def test_bias_scorer_error_handling(bias_scorer):
    with pytest.raises(ValueError):
        await bias_scorer.score("")
