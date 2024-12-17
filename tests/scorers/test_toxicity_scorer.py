"""Tests for toxicity scorer."""
import os
import pytest
from typing import Any, Dict, List, Optional
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from weave.scorers.moderation_scorer import ToxicityScorer
from tests.scorers.test_utils import generate_large_text


class TestToxicityScorer(ToxicityScorer):
    """Test-specific ToxicityScorer that uses local models."""
    def model_post_init(self, *args, **kwargs):
        """Override to use local model instead of downloading."""
        test_model_dir = os.path.join(os.path.dirname(__file__), "..", "weave_models")
        test_model_path = os.path.join(test_model_dir, "test-toxicity-scorer")
        self._local_model_path = test_model_path
        self._model = AutoModelForSequenceClassification.from_pretrained(
            test_model_path,
            num_labels=len(self._categories),
            problem_type="multi_label_classification"
        )
        self._tokenizer = AutoTokenizer.from_pretrained(test_model_path)
        self._model.to(self.device)
        self._model.eval()

    def predict_chunk(self, input_ids: "torch.Tensor") -> list[float]:
        """Override to handle multi-label output."""
        attention_mask = (input_ids != 0).long()
        outputs = self._model(input_ids=input_ids, attention_mask=attention_mask)
        predictions = torch.sigmoid(outputs.logits).squeeze().tolist()
        if isinstance(predictions, float):
            return [predictions]
        return predictions


@pytest.fixture
def toxicity_scorer():
    """Create a toxicity scorer instance using actual model."""
    return TestToxicityScorer(
        model_name_or_path="test-toxicity",
        name="test-toxicity",
        description="Test toxicity scorer",
        device="cpu",  # Use CPU for testing
        total_threshold=5,
        category_threshold=2
    )


def test_toxicity_scorer_large_input(toxicity_scorer):
    """Test toxicity scorer with large input."""
    large_text = generate_large_text(100000)  # Generate 100k characters
    result = toxicity_scorer.score(large_text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    assert isinstance(result["extras"], dict)
    assert all(cat in result["extras"] for cat in toxicity_scorer._categories)


def test_toxicity_scorer_error_handling(toxicity_scorer):
    """Test toxicity scorer error handling."""
    result = toxicity_scorer.score("")
    assert isinstance(result, dict)
    assert "flagged" in result
    assert "extras" in result
    assert all(cat in result["extras"] for cat in toxicity_scorer._categories)
    assert all(isinstance(score, (int, float)) for score in result["extras"].values())


def test_toxicity_scorer_race_origin(toxicity_scorer):
    """Test toxicity scorer for race/origin-based bias."""
    toxic_text = "People from that country are all criminals."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    assert "Race/Origin" in result["extras"]
    score = result["extras"]["Race/Origin"]
    assert isinstance(score, (int, float))
    assert result["flagged"] == (score >= toxicity_scorer.category_threshold)


def test_toxicity_scorer_gender_sex(toxicity_scorer):
    """Test toxicity scorer for gender/sex-based bias."""
    toxic_text = "Women are not capable of doing that job."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    assert "Gender/Sex" in result["extras"]
    score = result["extras"]["Gender/Sex"]
    assert isinstance(score, (int, float))
    assert result["flagged"] == (score >= toxicity_scorer.category_threshold)


def test_toxicity_scorer_religion(toxicity_scorer):
    """Test toxicity scorer for religious bias."""
    toxic_text = "That religious group is dangerous and untrustworthy."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    assert "Religion" in result["extras"]
    score = result["extras"]["Religion"]
    assert isinstance(score, (int, float))
    assert result["flagged"] == (score >= toxicity_scorer.category_threshold)


def test_toxicity_scorer_ability(toxicity_scorer):
    """Test toxicity scorer for ability-based bias."""
    toxic_text = "People with disabilities can't contribute to society."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    assert "Ability" in result["extras"]
    score = result["extras"]["Ability"]
    assert isinstance(score, (int, float))
    assert result["flagged"] == (score >= toxicity_scorer.category_threshold)


def test_toxicity_scorer_violence(toxicity_scorer):
    """Test toxicity scorer for violence content."""
    toxic_text = "I will hurt anyone who disagrees with me."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    assert "Violence" in result["extras"]
    score = result["extras"]["Violence"]
    assert isinstance(score, (int, float))
    assert result["flagged"] == (score >= toxicity_scorer.category_threshold)


def test_toxicity_scorer_multiple_categories(toxicity_scorer):
    """Test toxicity scorer with content triggering multiple categories."""
    toxic_text = "Women from that country are violent and dangerous."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    categories = ["Gender/Sex", "Race/Origin", "Violence"]
    for category in categories:
        assert category in result["extras"]
        score = result["extras"][category]
        assert isinstance(score, (int, float))

    should_flag = any(
        result["extras"][cat] >= toxicity_scorer.category_threshold
        for cat in categories
    )
    assert result["flagged"] == should_flag


def test_toxicity_scorer_clean(toxicity_scorer):
    """Test toxicity scorer with clean content."""
    clean_text = "The weather is nice today. Let's have a peaceful discussion."
    result = toxicity_scorer.score(clean_text)

    assert isinstance(result, dict)
    assert "extras" in result
    assert all(cat in result["extras"] for cat in toxicity_scorer._categories)
    assert all(
        isinstance(score, (int, float))
        for score in result["extras"].values()
    )
    should_flag = (
        sum(result["extras"].values()) >= toxicity_scorer.total_threshold
        or any(
            score >= toxicity_scorer.category_threshold
            for score in result["extras"].values()
        )
    )
    assert result["flagged"] == should_flag


def test_toxicity_scorer_total_threshold(toxicity_scorer):
    """Test toxicity scorer total threshold flagging."""
    toxic_text = "This text should have multiple mild issues that add up."
    result = toxicity_scorer.score(toxic_text)

    assert isinstance(result, dict)
    assert "extras" in result
    total_score = sum(result["extras"].values())
    max_category_score = max(result["extras"].values())

    should_flag = (
        total_score >= toxicity_scorer.total_threshold
        or max_category_score >= toxicity_scorer.category_threshold
    )
    assert result["flagged"] == should_flag
