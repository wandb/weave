import math

import pytest
from typing import List, Dict
from weave.scorers import BLEUScorer


def truncate(number, decimals=0):
    """Truncates a number to the specified number of decimal places without rounding."""
    factor = 10.0**decimals
    return math.trunc(number * factor) / factor


def test_bleu_scorer_initialization():
    # Test default initialization
    scorer = BLEUScorer()
    assert scorer.lowercase == False
    assert scorer.tokenize is None
    assert scorer.smooth_method == 'exp'
    assert scorer.smooth_value is None
    assert scorer.max_ngram_order == 4
    assert scorer.effective_order == True
    assert scorer.bleu is not None

    # Test initialization with custom parameters
    scorer = BLEUScorer(
        lowercase=True,
        tokenize='13a',
        smooth_method='add-k',
        smooth_value=1.0,
        max_ngram_order=2,
        effective_order=False
    )
    assert scorer.lowercase == True
    assert scorer.tokenize == '13a'
    assert scorer.smooth_method == 'add-k'
    assert scorer.smooth_value == 1.0
    assert scorer.max_ngram_order == 2
    assert scorer.effective_order == False
    assert scorer.bleu is not None

def test_bleu_scorer_score_method():
    scorer = BLEUScorer()
    output = "The cat is on the mat."
    ground_truths = ["The cat is on the mat.", "There is a cat on the mat."]

    # Test score method with exact match
    result = scorer.score(ground_truths=ground_truths, output=output)
    assert isinstance(result, dict)
    assert truncate(result["sentence_bleu"], 1) == 100.0
    assert truncate(result["sentence_bp"], 1) == 1.0
    assert result["output_pred"] == output
    assert result["output_refs"] == ground_truths

    # Test score method with partial match
    output = "The cat sat on the mat."
    result = scorer.score(ground_truths=ground_truths, output=output)
    assert result["sentence_bleu"] < 100.0
    assert result["output_pred"] == output

    # Test with single reference
    output = "The dog is in the house."
    ground_truths = "The dog is outside."
    result = scorer.score(ground_truths=ground_truths, output=output)
    assert isinstance(result["output_refs"], list)
    assert result["output_refs"] == [ground_truths]

def test_bleu_scorer_score_method_invalid_input():
    scorer = BLEUScorer()
    output = "Sample output"

    # Test with invalid ground_truths type
    with pytest.raises(
        AssertionError, match="`ground_truths` must be a list of strings."
    ):
        scorer.score(ground_truths=123, output=output)

def test_bleu_scorer_summarize_method():
    scorer = BLEUScorer()
    score_rows = [
        {
            "sentence_bleu": 100.0,
            "sentence_bp": 1.0,
            "output_pred": "The cat is on the mat.",
            "output_refs": ["The cat is on the mat."]
        },
        {
            "sentence_bleu": 50.0,
            "sentence_bp": 0.8,
            "output_pred": "A dog is in the yard.",
            "output_refs": ["The dog is in the yard."]
        },
        {
            "sentence_bleu": 0.0,
            "sentence_bp": 0.5,
            "output_pred": "Completely different sentence.",
            "output_refs": ["No match here."]
        }
    ]

    result = scorer.summarize(score_rows)
    assert isinstance(result, dict)
    assert "corpus_level" in result
    assert "sentence_level" in result
    assert truncate(result["sentence_level"]["bleu"], 1) == 50.0

    # Verify corpus-level BLEU score
    corpus_bleu = result["corpus_level"]["bleu"]
    assert truncate(corpus_bleu, 1) >= 0.0 and truncate(corpus_bleu, 1) <= 100.0

def test_bleu_scorer_summarize_method_empty_input():
    scorer = BLEUScorer()
    score_rows = []
    result = scorer.summarize(score_rows)
    assert result == {}

def test_bleu_scorer_summarize_method_invalid_score_rows():
    scorer = BLEUScorer()
    score_rows = ["invalid", 123, None]
    with pytest.raises(AssertionError):
        scorer.summarize(score_rows)

def test_bleu_scorer_corpus_score():
    scorer = BLEUScorer()
    score_rows = [
        {
            "sentence_bleu": 100.0,
            "sentence_bp": 1.0,
            "output_pred": "The cat is on the mat.",
            "output_refs": ["The cat is on the mat."]
        },
        {
            "sentence_bleu": 50.0,
            "sentence_bp": 0.8,
            "output_pred": "A dog is in the yard.",
            "output_refs": ["The dog is in the yard.", "A dog is outside."]
        }
    ]

    result = scorer.summarize(score_rows)
    print(result)
    corpus_bleu = result["corpus_level"]["bleu"]
    assert truncate(corpus_bleu, 1) == 100.0

def test_bleu_scorer_with_different_tokenizer():
    # Test BLEUScorer with a different tokenizer
    scorer = BLEUScorer(tokenize='char')
    output = "abcd"
    ground_truths = ["abcf"]

    result = scorer.score(ground_truths=ground_truths, output=output)
    assert result["sentence_bleu"] < 100.0

def test_bleu_scorer_effective_order():
    # Test BLEUScorer with effective_order set to False
    scorer = BLEUScorer(effective_order=False)
    output = "The cat"
    ground_truths = ["The cat is on the mat."]

    result = scorer.score(ground_truths=ground_truths, output=output)
    # With effective_order=False, the score might be lower due to missing higher-order n-grams
    assert result["sentence_bleu"] < 100.0

def test_bleu_scorer_smooth_method():
    # Test BLEUScorer with different smoothing methods
    scorer = BLEUScorer(smooth_method='floor', smooth_value=0.1)
    output = "The cat sat on the mat."
    ground_truths = ["The cat is on the mat."]

    result = scorer.score(ground_truths=ground_truths, output=output)
    assert result["sentence_bleu"] > 0.0

    # Test with invalid smoothing method
    with pytest.raises(ValueError):
        BLEUScorer(smooth_method='invalid_method')
