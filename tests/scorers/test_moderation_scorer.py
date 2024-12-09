from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import torch
from torch import Tensor

from weave.scorers.moderation_scorer import RollingWindowScorer


# Define a concrete subclass for testing since RollingWindowScorer is abstract
class TestRollingWindowScorer(RollingWindowScorer):
    def model_post_init(self, __context: Any) -> None:
        """Mock implementation for testing."""
        self._tokenizer = MagicMock()
        self.device = "cpu"

    async def score(self, output: str) -> dict[str, Any]:
        """Mock score method for testing."""
        return {}


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
    scorer.predict_chunk = MagicMock(return_value=[0, 1])

    with patch.object(scorer, "tokenize_input", return_value=input_ids):
        with patch.object(
            scorer, "predict_long", return_value=[0, 1]
        ) as mock_predict_long:
            predictions = scorer.predict(prompt)
            mock_predict_long.assert_called_with(input_ids)
            assert predictions == [0, 1]


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
