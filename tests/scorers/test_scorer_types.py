import pytest
import torch
from torch import Tensor

from tests.scorers.test_utils import RandomTokenizer
from weave.scorers.scorer_types import RollingWindowScorer

torch.manual_seed(42)


class MockModel:
    def __call__(self, input_ids: Tensor) -> list[float]:
        total = sum(input_ids[0])
        return [input_ids.shape[1], total.item()]


class RollingWindowScorerMock(RollingWindowScorer):
    max_tokens: int = 10
    overlap: int = 0

    def load_model(self):
        self._model = MockModel()

    def load_tokenizer(self):
        self._tokenizer = RandomTokenizer()

    def predict_chunk(self, input_ids: Tensor) -> list[float]:
        return self._model(input_ids)


@pytest.fixture
def rolling_window_scorer():
    scorer_instance = RollingWindowScorerMock()
    return scorer_instance


@pytest.mark.asyncio
async def test_aggregate_predictions(rolling_window_scorer):
    rolling_window_scorer.aggregation_method = "max"
    all_predictions = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    expected = [7, 8, 9]
    result = rolling_window_scorer._aggregate_predictions(all_predictions)
    assert result == expected
    # mean
    rolling_window_scorer.aggregation_method = "mean"
    expected = [4.0, 5.0, 6.0]
    result = rolling_window_scorer._aggregate_predictions(all_predictions)
    assert result == expected


@pytest.mark.asyncio
async def test_predict_long(rolling_window_scorer):
    input_ids = Tensor([list(range(100))])
    rolling_window_scorer.aggregation_method = "mean"
    result = rolling_window_scorer._predict_long(input_ids)
    assert result == [
        10,
        495,
    ]  # chunks of length 10, average of 99 * 100 / (2 * 10) = 495

    rolling_window_scorer.aggregation_method = "max"
    result = rolling_window_scorer._predict_long(input_ids)
    assert result == [
        10,
        945,
    ]  # chunks of length 10, max = 99 + 98 + ... + 91 + 90 = 955


@pytest.mark.asyncio
async def test_predict_long_overlap(rolling_window_scorer):
    input_ids = Tensor([list(range(10))])
    rolling_window_scorer.max_tokens = 5
    rolling_window_scorer.aggregation_method = "mean"
    rolling_window_scorer.overlap = 2
    result = rolling_window_scorer._predict_long(input_ids)
    # Chunks are:
    # stride = 5 - 2 = 3
    # [0, 1, 2, 3, 4] -> sum = 10
    # [3, 4, 5, 6, 7] -> sum = 25
    # [6, 7, 8, 9] -> sum = 30
    # Average of 10, 25, 30 = 21.6666
    # Average length (5, 5, 4) = 4.66666
    assert result == pytest.approx([4.66, 21.66], rel=1e-2)
    rolling_window_scorer.aggregation_method = "max"
    result = rolling_window_scorer._predict_long(input_ids)
    assert result == [5, 30]
