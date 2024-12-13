from typing import Any
import pytest
import torch
from torch import Tensor
from unittest.mock import MagicMock, patch

from weave.scorers.moderation_scorer import RollingWindowScorer, ToxicityScorer, BiasScorer
from tests.scorers.test_utils import generate_large_text
from pydantic import PrivateAttr, Field


class TestRollingWindowScorer(RollingWindowScorer):
    """Test implementation of RollingWindowScorer."""
    _model: Any = PrivateAttr(default_factory=MagicMock)
    _tokenizer: Any = PrivateAttr(default_factory=MagicMock)
    device: str = Field(default="cpu")
    aggregation_method: str = Field(default="max")
    tokenize_input: Any = Field(default_factory=lambda: None)
    predict_chunk: Any = Field(default_factory=lambda: None)

    def model_post_init(self, __context: Any) -> None:
        """Mock implementation for testing."""
        super().model_post_init(__context)
        self._model.return_value = [0.5, 0.3]  # Default prediction values
        self._tokenizer.return_value = MagicMock(input_ids=torch.tensor([[1, 2, 3]]))

        def mock_tokenize(text: str, **kwargs) -> Tensor:
            return self._tokenizer(text, return_tensors="pt", truncation=False).input_ids

        def mock_predict(input_ids: Tensor) -> list[float]:
            return self._model(input_ids)

        self.tokenize_input = mock_tokenize
        self.predict_chunk = mock_predict

    async def score(self, output: str) -> dict[str, Any]:
        """Mock score method for testing."""
        return {"flagged": False, "extras": {"category": "test", "score": 0.5}}


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
    """Create a toxicity scorer for testing."""
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    # Mock model loading functions
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("weave.scorers.llm_utils.scorer_model_paths", lambda *args: {"toxicity": "mock_path"})
    monkeypatch.setattr("weave.scorers.llm_utils.set_device", lambda *args: "cpu")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: "mock_path")

    # Create mock model and tokenizer
    mock_model = MagicMock()
    def mock_predict(input_ids):
        text = toxicity_scorer._tokenizer.decode(input_ids[0])
        if any(word in text.lower() for word in ["hate", "kill", "stupid", "violent"]):
            return [0.9, 0.8, 0.7, 0.8, 0.9]  # High toxicity scores
        return [0.1, 0.2, 0.1, 0.1, 0.1]  # Low toxicity scores
    mock_model.side_effect = mock_predict
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = MagicMock(input_ids=torch.tensor([[1, 2, 3]]))

    scorer = ToxicityScorer(
        model_name_or_path="wandb/toxicity_scorer",
        device="cpu",
        name="test-toxicity",
        description="Test toxicity scorer",
        column_map={"output": "text"}
    )

    # Set up model attributes
    monkeypatch.setattr(scorer, "_model", mock_model)
    monkeypatch.setattr(scorer, "_tokenizer", mock_tokenizer)
    monkeypatch.setattr(scorer, "model_post_init", lambda *args: None)
    monkeypatch.setattr(scorer, "__private_attributes__", {})
    monkeypatch.setattr(scorer, "__pydantic_private__", {})
    monkeypatch.setattr(scorer, "__pydantic_fields__", {"_model": None, "_tokenizer": None})
    monkeypatch.setattr(scorer, "__pydantic_extra__", {})
    return scorer


@pytest.fixture
def bias_scorer(monkeypatch):
    """Create a bias scorer for testing."""
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))

    # Mock model loading functions
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("weave.scorers.llm_utils.scorer_model_paths", lambda *args: {"bias": "mock_path"})
    monkeypatch.setattr("weave.scorers.llm_utils.set_device", lambda *args: "cpu")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: "mock_path")

    # Create mock model and tokenizer
    mock_model = MagicMock()
    def mock_predict(input_ids):
        text = bias_scorer._tokenizer.decode(input_ids[0])
        if any(word in text.lower() for word in ["men are", "women are", "stereotype"]):
            return [0.9, 0.8]  # High bias scores
        return [0.1, 0.1]  # Low bias scores
    mock_model.side_effect = mock_predict
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = MagicMock(input_ids=torch.tensor([[1, 2, 3]]))

    scorer = BiasScorer(
        model_name_or_path="wandb/bias_scorer",
        device="cpu",
        name="test-bias",
        description="Test bias scorer",
        column_map={"output": "text"}
    )

    # Set up model attributes
    monkeypatch.setattr(scorer, "_model", mock_model)
    monkeypatch.setattr(scorer, "_tokenizer", mock_tokenizer)
    monkeypatch.setattr(scorer, "model_post_init", lambda *args: None)
    monkeypatch.setattr(scorer, "__private_attributes__", {})
    monkeypatch.setattr(scorer, "__pydantic_private__", {})
    monkeypatch.setattr(scorer, "__pydantic_fields__", {"_model": None, "_tokenizer": None})
    monkeypatch.setattr(scorer, "__pydantic_extra__", {})
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


@pytest.mark.asyncio
async def test_toxicity_scorer_flags_toxic(toxicity_scorer):
    toxic_text = "You are a terrible person and I hate you."

    def mock_predict(text):
        return [0.8, 0.7, 0.6, 0.5, 0.4]  # High scores for toxic categories

    toxicity_scorer.predict = mock_predict
    result = await toxicity_scorer.score(toxic_text)

    assert result["flagged"] == True
    assert any(score >= toxicity_scorer.category_threshold
              for score in result["extras"].values())


@pytest.mark.asyncio
async def test_toxicity_scorer_passes_clean(toxicity_scorer):
    clean_text = "Have a wonderful day!"

    def mock_predict(text):
        return [0.1, 0.2, 0.1, 0.1, 0.1]  # Low scores for all categories

    toxicity_scorer.predict = mock_predict
    result = await toxicity_scorer.score(clean_text)

    assert result["flagged"] == False
    assert all(score < toxicity_scorer.category_threshold
              for score in result["extras"].values())


@pytest.mark.asyncio
async def test_bias_scorer_flags_biased(bias_scorer):
    biased_text = "Women are not good at math and science."

    def mock_predict(text):
        return [0.9, 0.8]  # High scores for bias categories

    bias_scorer.predict = mock_predict
    result = await bias_scorer.score(biased_text)

    assert result["flagged"] == True
    assert result["extras"]["gender_bias"] == True
    assert result["extras"]["racial_bias"] == True


@pytest.mark.asyncio
async def test_bias_scorer_passes_unbiased(bias_scorer):
    unbiased_text = "People of all backgrounds can excel in STEM fields."

    def mock_predict(text):
        return [0.2, 0.1]  # Low scores for bias categories

    bias_scorer.predict = mock_predict
    result = await bias_scorer.score(unbiased_text)

    assert result["flagged"] == False
    assert result["extras"]["gender_bias"] == False
    assert result["extras"]["racial_bias"] == False
