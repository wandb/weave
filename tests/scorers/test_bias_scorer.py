"""Tests for bias scorer."""
import os
import pytest
from typing import Any, Dict, List, Optional
import torch
from transformers import BertForSequenceClassification, BertTokenizer

from weave.scorers.moderation_scorer import BiasScorer
from tests.scorers.test_utils import generate_large_text


class TestBiasScorer(BiasScorer):
    """Test-specific BiasScorer that uses local models."""
    def model_post_init(self, *args, **kwargs):
        """Override to use local model instead of downloading."""
        test_model_dir = os.path.join(os.path.dirname(__file__), "..", "weave_models")
        test_model_path = os.path.join(test_model_dir, "test-bias-scorer")
        self._local_model_path = test_model_path
        self._model = BertForSequenceClassification.from_pretrained(test_model_path)
        self._tokenizer = BertTokenizer.from_pretrained(test_model_path)
        self._model.to(self.device)
        self._model.eval()


@pytest.fixture
def bias_scorer():
    """Create a bias scorer instance using actual model."""
    return TestBiasScorer(
        model_name_or_path="bert-base-uncased",  # Original model name
        name="test-bias",
        description="Test bias scorer",
        column_map={"output": "text"},
        device="cpu"  # Use CPU for testing
    )


def test_bias_scorer_large_input(bias_scorer):
    """Test bias scorer with large input."""
    large_text = generate_large_text(100000)  # Generate 100k characters
    result = bias_scorer.score(large_text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    assert isinstance(result["extras"], dict)
    assert all(cat in result["extras"] for cat in bias_scorer._categories)


def test_bias_scorer_error_handling(bias_scorer):
    """Test bias scorer error handling."""
    result = bias_scorer.score("")
    assert isinstance(result, dict)
    assert "flagged" in result
    assert "extras" in result


def test_bias_scorer_processes_biased(bias_scorer):
    """Test bias scorer processes biased content."""
    biased_text = "Women are not good at math and science."
    result = bias_scorer.score(biased_text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    assert isinstance(result["extras"], dict)
    assert all(cat in result["extras"] for cat in bias_scorer._categories)


def test_bias_scorer_processes_unbiased(bias_scorer):
    """Test bias scorer processes unbiased content."""
    unbiased_text = "Everyone deserves equal opportunities in education."
    result = bias_scorer.score(unbiased_text)

    assert isinstance(result, dict)
    assert "flagged" in result
    assert isinstance(result["flagged"], bool)
    assert "extras" in result
    assert isinstance(result["extras"], dict)
    assert all(cat in result["extras"] for cat in bias_scorer._categories)
