"""Tests for scorer validation and cleanup."""
import pytest
import gc
import torch
from weave.scorers import (
    BLEUScorer,
    RougeScorer,
    CoherenceScorer,
    ContextRelevanceScorer,
    RobustnessScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
)


def get_gpu_memory_usage():
    """Get current GPU memory usage if available."""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated()
    return 0


@pytest.fixture
def cleanup_between_tests():
    """Fixture to clean up resources between tests."""
    yield
    
    # Force garbage collection
    gc.collect()
    
    # Clear CUDA cache if available
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@pytest.mark.parametrize("scorer_class", [
    CoherenceScorer,
    ContextRelevanceScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
])
def test_model_cleanup(scorer_class, cleanup_between_tests):
    """Test that models are properly cleaned up after use."""
    initial_memory = get_gpu_memory_usage()
    
    # Create and use scorer
    scorer = scorer_class(
        model_name_or_path=f"wandb/{scorer_class.__name__.lower()}",
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    
    # Use the scorer
    _ = scorer.score(
        input="Test input",
        output="Test output"
    )
    
    # Delete the scorer
    del scorer
    gc.collect()
    
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        final_memory = get_gpu_memory_usage()
        
        # Allow for small memory differences due to PyTorch internals
        assert abs(final_memory - initial_memory) < 1024, (
            f"Memory leak detected: {(final_memory - initial_memory) / 1024 / 1024:.2f}MB"
        )


@pytest.mark.parametrize("scorer_class", [
    CoherenceScorer,
    ContextRelevanceScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
])
def test_model_input_validation(scorer_class):
    """Test input validation for model-based scorers."""
    scorer = scorer_class(
        model_name_or_path=f"wandb/{scorer_class.__name__.lower()}",
        device="cpu"
    )
    
    # Test input length validation
    very_long_input = "test " * 10000
    with pytest.raises(ValueError) as exc_info:
        scorer.score(
            input=very_long_input,
            output=very_long_input
        )
    assert "input too long" in str(exc_info.value).lower()
    
    # Test input type validation
    invalid_inputs = [
        None,
        123,
        ["not", "a", "string"],
        {"not": "valid"},
    ]
    
    for invalid_input in invalid_inputs:
        with pytest.raises((ValueError, TypeError)) as exc_info:
            scorer.score(
                input=invalid_input,
                output="Valid output"
            )
        assert "invalid input" in str(exc_info.value).lower()


@pytest.mark.parametrize("scorer_class", [
    BLEUScorer,
    RougeScorer,
    RobustnessScorer,
])
def test_metric_scorer_validation(scorer_class):
    """Test validation for metric-based scorers."""
    scorer = scorer_class()
    
    # Test with invalid inputs
    invalid_cases = [
        (None, None),
        (123, "string"),
        ("string", 123),
        (["list"], "string"),
        ("string", ["list"]),
    ]
    
    for input_val, output_val in invalid_cases:
        with pytest.raises((ValueError, TypeError)) as exc_info:
            if scorer_class in [BLEUScorer, RougeScorer]:
                scorer.score(
                    ground_truths=[output_val] if output_val else None,
                    output=output_val
                )
            else:
                scorer.score(
                    input=input_val,
                    output=output_val
                )
        assert any(msg in str(exc_info.value).lower() for msg in [
            "invalid input",
            "invalid type",
            "must be string"
        ])


@pytest.mark.parametrize("scorer_class", [
    CoherenceScorer,
    ContextRelevanceScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
])
def test_model_output_validation(scorer_class):
    """Test that model outputs are properly validated."""
    scorer = scorer_class(
        model_name_or_path=f"wandb/{scorer_class.__name__.lower()}",
        device="cpu"
    )
    
    result = scorer.score(
        input="Test input",
        output="Test output"
    )
    
    # Verify result format
    assert isinstance(result, dict), "Result should be a dictionary"
    
    # Verify required fields based on scorer type
    if scorer_class == CoherenceScorer:
        assert "coherent" in result
        assert isinstance(result["coherent"], bool)
        assert "coherence_score" in result
        assert 0 <= result["coherence_score"] <= 1
        
    elif scorer_class == ToxicScorer:
        assert "toxic" in result
        assert isinstance(result["toxic"], bool)
        assert "toxicity_score" in result
        assert 0 <= result["toxicity_score"] <= 1
        
    elif scorer_class == GenderRaceBiasScorer:
        assert "biased" in result
        assert isinstance(result["biased"], bool)
        assert "bias_score" in result
        assert 0 <= result["bias_score"] <= 1


@pytest.mark.parametrize("scorer_class", [
    CoherenceScorer,
    ContextRelevanceScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
])
def test_model_config_validation(scorer_class):
    """Test validation of model configuration."""
    # Test invalid model path
    with pytest.raises(ValueError) as exc_info:
        scorer_class(
            model_name_or_path="invalid/model/path",
            device="cpu"
        )
    assert "model" in str(exc_info.value).lower()
    
    # Test invalid device
    with pytest.raises(ValueError) as exc_info:
        scorer_class(
            model_name_or_path=f"wandb/{scorer_class.__name__.lower()}",
            device="invalid_device"
        )
    assert "device" in str(exc_info.value).lower()
    
    # Test valid configuration
    scorer = scorer_class(
        model_name_or_path=f"wandb/{scorer_class.__name__.lower()}",
        device="cpu"
    )
    assert scorer is not None


@pytest.mark.parametrize("scorer_class", [
    CoherenceScorer,
    ContextRelevanceScorer,
    ToxicScorer,
    GenderRaceBiasScorer,
])
def test_score_normalization(scorer_class):
    """Test that scores are properly normalized."""
    scorer = scorer_class(
        model_name_or_path=f"wandb/{scorer_class.__name__.lower()}",
        device="cpu"
    )
    
    # Test with various inputs
    test_cases = [
        "This is a normal input.",
        "This is a very " + "long " * 100 + "input.",
        "Special characters: !@#$%^&*()",
        "Unicode characters: こんにちは",
    ]
    
    for test_input in test_cases:
        result = scorer.score(
            input="Test prompt",
            output=test_input
        )
        
        # Check that all scores are normalized between 0 and 1
        for key, value in result.items():
            if isinstance(value, (int, float)):
                assert 0 <= value <= 1, (
                    f"Score {key}={value} not normalized between 0 and 1"
                )