import os
import tempfile
import time
from unittest.mock import MagicMock, patch
from urllib3.exceptions import NewConnectionError
from wandb.errors import CommError
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log, retry_if_exception_type
import logging

import psutil
import pytest
import torch

import weave
from tests.scorers.test_utils import generate_context_and_output
from weave.scorers import HallucinationScorer
from weave.scorers.llm_utils import MODEL_PATHS, download_model

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    retry=retry_if_exception_type((CommError, NewConnectionError)),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.INFO)
)
def download_model_with_retry(model_path):
    """Download model with retry logic"""
    print(f"Attempting to download model from: {model_path}")
    model_dir = download_model(model_path)
    print(f"Model downloaded to: {model_dir}")
    return model_dir

@pytest.fixture(scope="session", autouse=True)
def setup_test_models():
    """Download required models before any tests run"""
    print("\nDownloading required models...")
    model_path = MODEL_PATHS["hallucination_hhem_scorer"]
    return download_model_with_retry(model_path)


@pytest.fixture
def mock_model_setup(monkeypatch, setup_test_models):
    """Mock model setup and dependencies"""
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr(
        "wandb.Api", lambda: MagicMock(project=lambda *args: mock_project)
    )

    return setup_test_models  # Use the already downloaded model path


@pytest.fixture
def hallucination_scorer(mock_model_setup, monkeypatch):
    """Create a test instance of HallucinationScorer with HHEM model"""
    scorer = HallucinationScorer()
    return scorer


def test_model_initialization(mock_model_setup):
    """Test model initialization with different configurations"""
    # Test 1: Initialize with no file path (should download automatically)
    scorer = HallucinationScorer(
        device="cpu",
        use_hhem=True,
    )
    assert scorer.device == "cpu"
    assert scorer._local_model_path is not None
    assert os.path.exists(scorer._local_model_path)

    # Test 2: Initialize with local file path (using the path from mock_model_setup)
    print(f"\nUsing local model path: {mock_model_setup}")
    print(f"Model directory exists: {os.path.exists(mock_model_setup)}")
    
    scorer_local = HallucinationScorer(
        model_name_or_path=mock_model_setup,
        device="cpu",
        use_hhem=True,
    )
    assert scorer_local.device == "cpu"
    assert scorer_local.model_name_or_path == mock_model_setup
    assert os.path.exists(scorer_local.model_name_or_path)

    # Test CUDA initialization if available
    if torch.cuda.is_available():
        scorer_cuda = HallucinationScorer(
            model_name_or_path=mock_model_setup,
            device="cuda",
        )
        assert scorer_cuda.device == "cuda"
    else:
        with pytest.raises(ValueError):
            HallucinationScorer(
                model_name_or_path=mock_model_setup,
                device="cuda"
            )


def test_model_loading_performance(mock_model_setup):
    """Test model loading performance and memory usage"""
    process = psutil.Process()
    
    # First download the model if needed (don't include in timing)
    model_path = download_model_with_retry(MODEL_PATHS["hallucination_hhem_scorer"])
    
    # Test model loading performance
    initial_memory = process.memory_info().rss
    start_time = time.time()
    
    scorer = HallucinationScorer(
        model_name_or_path=model_path,  # Use the already downloaded model
        device="cpu"
    )
    load_time = time.time() - start_time

    # Performance checks
    assert load_time < 15  # Model should load within 15 seconds

    # Memory usage check for loading
    load_memory = process.memory_info().rss
    load_memory_increase = load_memory - initial_memory
    assert (
        load_memory_increase < 2 * 1024 * 1024 * 1024
    )  # Should use less than 2GB additional memory for loading

    # Test inference memory usage
    query = "What is this text about?"
    context, output = generate_context_and_output(1000)  # Medium-sized input
    
    inference_start_memory = process.memory_info().rss
    _ = scorer.score(query=query, context=context, output=output)
    inference_end_memory = process.memory_info().rss
    
    inference_memory_increase = inference_end_memory - inference_start_memory
    assert (
        inference_memory_increase < 1 * 1024 * 1024 * 1024
    )  # Should use less than 1GB additional memory during inference
    
    # Check memory is released after inference
    time.sleep(1)  # Give GC a chance to run
    final_memory = process.memory_info().rss
    assert (
        final_memory - inference_start_memory < 100 * 1024 * 1024
    )  # Should release most memory after inference


@pytest.mark.asyncio
async def test_basic_output_structure(hallucination_scorer):
    """Test that the scorer returns the expected output structure"""
    query = "What is this text about?"
    context, output = generate_context_and_output(100)  # Small test case
    
    result = hallucination_scorer.score(
        query=query, context=context, output=output
    )
    
    # Basic structure validation
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "flagged" in result, "Result should contain 'flagged' key"
    assert "extras" in result, "Result should contain 'extras' key"
    assert "score" in result["extras"], "Result should contain 'score' in extras"
    
    # Type validation
    assert isinstance(result["flagged"], bool), "'flagged' should be a boolean"
    assert isinstance(result["extras"]["score"], float), "'score' should be a float"
    assert 0 <= result["extras"]["score"] <= 1, "'score' should be between 0 and 1"


# @pytest.mark.asyncio
# async def test_scoring_latency(hallucination_scorer):
#     """Test scoring latency with different input sizes"""
#     latencies = []

#     for size in [100, 1000, 10000]:
#         logging.info(f"Testing input size: {size} tokens")
#         query = "What is this text about?"
#         context, output = generate_context_and_output(size)

#         start_time = time.time()
#         _ = hallucination_scorer.score(
#             query=query, context=context, output=output
#         )
#         latency = time.time() - start_time
#         latencies.append(latency)

#     for i in range(0, len(latencies)):
#         assert latencies[i] < 10


# @pytest.mark.asyncio
# async def test_memory_usage_during_scoring(hallucination_scorer):
#     """Test memory usage during scoring operations"""
#     process = psutil.Process()
#     initial_memory = process.memory_info().rss
#     memory_measurements = []

#     for size in [1000, 10000, 100000]:
#         query = "What is this text about?"
#         context, output = generate_context_and_output(size)

#         _ = await hallucination_scorer.score(
#             query=query, context=context, output=output
#         )

#         current_memory = process.memory_info().rss
#         memory_measurements.append(current_memory - initial_memory)

#     # Memory usage should not grow exponentially
#     for i in range(1, len(memory_measurements)):
#         ratio = memory_measurements[i] / max(memory_measurements[i - 1], 1)
#         assert ratio < 5  # Memory growth should be less than 5x between sizes


@pytest.mark.asyncio
async def test_resource_cleanup(hallucination_scorer):
    """Test proper cleanup of resources after scoring"""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    initial_handles = len(process.open_files())

    # Perform multiple scoring operations
    for _ in range(5):
        query = "What is this text about?"
        context, output = generate_context_and_output(100)

        _ = hallucination_scorer.score(
            query=query, context=context, output=output
        )

    # Check resource cleanup
    final_memory = process.memory_info().rss
    final_handles = len(process.open_files())

    # Memory and file handles should be properly cleaned up
    assert final_memory - initial_memory < 100 * 1024 * 1024  # Less than 100MB growth
    assert final_handles <= initial_handles + 1  # Allow for one additional handle


@pytest.mark.asyncio
async def test_model_accuracy(hallucination_scorer):
    """Test model accuracy with known hallucination cases"""
    test_cases = [
        {
            "query": "What color is the sky?",
            "context": "The sky is blue.",
            "output": "The sky is green with purple polka dots.",
            "expected_flagged": True,
        },
        {
            "query": "What color is the sky?",
            "context": "The sky is blue.",
            "output": "The sky is blue.",
            "expected_flagged": False,
        },
        {
            "query": "Describe the weather.",
            "context": "It's a sunny day with no clouds.",
            "output": "It's a sunny day.",
            "expected_flagged": False,
        },
        {
            "query": "What did John eat?",
            "context": "John had a sandwich for lunch.",
            "output": "John had pizza for lunch.",
            "expected_flagged": True,
        },
    ]

    for case in test_cases:
        result = hallucination_scorer.score(
            query=case["query"], context=case["context"], output=case["output"]
        )
        assert result["flagged"] == case["expected_flagged"]


@pytest.mark.asyncio
async def test_integration_with_evaluation(hallucination_scorer):
    """Test integration with Weave's evaluation framework"""
    dataset = [
        {
            "query": "What color is the sky?",
            "context": "The sky is blue.",
            "response": "The sky is blue.",
        },
        {
            "query": "What's the weather?",
            "context": "It's sunny with no clouds.",
            "response": "It's sunny with no clouds.",
        },
    ]

    @weave.op
    def model(query, context, response):
        return response

    evaluation = weave.Evaluation(dataset=dataset, scorers=[hallucination_scorer])

    result = await evaluation.evaluate(model)
    assert "HallucinationScorer" in result
    assert isinstance(result["HallucinationScorer"]["flagged"]["true_count"], int)


# @pytest.mark.asyncio
# async def test_large_input_handling(hallucination_scorer):
#     """Test handling of large inputs"""
#     query = "What is the story about?"
#     context, output = generate_context_and_output(100_000, context_ratio=0.8)

#     start_time = time.time()
#     result = await hallucination_scorer.score(
#         query=query, context=context, output=output
#     )
#     end_time = time.time()

#     # Performance checks
#     assert end_time - start_time < 60  # Should complete within 60 seconds

#     # Memory checks
#     process = psutil.Process()
#     memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
#     assert memory_usage < 4096  # Should use less than 4GB RAM


def test_error_handling(hallucination_scorer):
    """Test error handling for various edge cases"""
    # Test empty inputs
    with pytest.raises(ValueError):
        hallucination_scorer.score(query="", context="", output="")

    # Test invalid device
    with pytest.raises(ValueError):
        HallucinationScorer(model_name_or_path="test", device="invalid_device")

    # Test missing model path
    with pytest.raises(ValueError):
        HallucinationScorer(model_name_or_path="", device="cpu")

    # Test invalid input types
    with pytest.raises(TypeError):
        hallucination_scorer.score(query=123, context="test", output="test")


@pytest.mark.asyncio
async def test_model_inference_settings(mock_model_setup):
    """Test model inference with different settings"""
    scorer = HallucinationScorer(
        model_name_or_path=mock_model_setup,
        device="cpu",
        do_sample=True,
        temperature=0.8,
        top_k=50,
        top_p=90,  # Changed to integer
    )

    assert scorer.do_sample is True
    assert scorer.temperature == 0.8
    assert scorer.top_k == 50
    assert scorer.top_p == 90

    # Test with different max length settings
    scorer.model_max_length = 4096
    query = "Test query"
    context = "Test context"
    output = "Test output"

    result = await scorer.score(query=query, context=context, output=output)
    assert isinstance(result, dict)
    assert "flagged" in result
    assert "extras" in result
    assert "score" in result["extras"]
