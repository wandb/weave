import os
import pytest
import time
import torch
import psutil
import tempfile
from unittest.mock import MagicMock, patch

import weave
from weave.scorers import HallucinationScorer
from tests.scorers.test_utils import generate_large_text, generate_context_and_output


@pytest.fixture
def mock_model_setup(monkeypatch):
    """Mock model setup and dependencies"""
    # Create temporary model files
    temp_dir = tempfile.mkdtemp()
    model_dir = os.path.join(temp_dir, "model")
    os.makedirs(model_dir, exist_ok=True)
    
    # Create config.json with model_type
    config = {
        "model_type": "gpt2",  # Using a known model type
        "architectures": ["GPT2ForSequenceClassification"],
        "vocab_size": 50257,
        "n_positions": 1024,
        "n_ctx": 1024,
        "n_embd": 768,
        "n_layer": 12,
        "n_head": 12,
        "activation_function": "gelu_new",
        "resid_pdrop": 0.1,
        "embd_pdrop": 0.1,
        "attn_pdrop": 0.1,
        "layer_norm_epsilon": 1e-5,
        "initializer_range": 0.02,
        "scale_attn_weights": True,
        "use_cache": True,
        "bos_token_id": 50256,
        "eos_token_id": 50256,
        "num_labels": 2  # For sequence classification
    }
    import json
    with open(os.path.join(model_dir, "config.json"), "w") as f:
        json.dump(config, f)
    
    # Create a dummy pytorch_model.bin file
    import torch
    state_dict = {
        "transformer.wte.weight": torch.randn(50257, 768),
        "transformer.wpe.weight": torch.randn(1024, 768),
        "transformer.h.0.ln_1.weight": torch.randn(768),
        "transformer.h.0.ln_1.bias": torch.randn(768),
        "transformer.h.0.attn.c_attn.weight": torch.randn(768, 2304),
        "transformer.h.0.attn.c_attn.bias": torch.randn(2304),
        "transformer.h.0.attn.c_proj.weight": torch.randn(768, 768),
        "transformer.h.0.attn.c_proj.bias": torch.randn(768),
        "transformer.h.0.ln_2.weight": torch.randn(768),
        "transformer.h.0.ln_2.bias": torch.randn(768),
        "transformer.h.0.mlp.c_fc.weight": torch.randn(768, 3072),
        "transformer.h.0.mlp.c_fc.bias": torch.randn(3072),
        "transformer.h.0.mlp.c_proj.weight": torch.randn(3072, 768),
        "transformer.h.0.mlp.c_proj.bias": torch.randn(768),
        "transformer.ln_f.weight": torch.randn(768),
        "transformer.ln_f.bias": torch.randn(768),
        "score.weight": torch.randn(2, 768),  # For sequence classification
        "score.bias": torch.randn(2)  # For sequence classification
    }
    torch.save(state_dict, os.path.join(model_dir, "pytorch_model.bin"))
    
    # Mock model loading functions
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args: model_dir)
    monkeypatch.setattr("weave.scorers.llm_utils.MODEL_PATHS", 
                       {"hallucination_hhem_scorer": model_dir})
    monkeypatch.setattr("weave.scorers.llm_utils.set_device", lambda *args: "cpu")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: model_dir)
    
    # Mock wandb login and project
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))
    
    return model_dir


@pytest.fixture
def hallucination_scorer(mock_model_setup, monkeypatch):
    """Create a test instance of HallucinationScorer with HHEM model"""
    scorer = HallucinationScorer(
        model_name_or_path=mock_model_setup,
        device="cpu",
        name="test-hallucination",
        description="Test hallucination scorer",
        column_map={"output": "text"},
        use_hhem=True,  # Always use HHEM model
        model_max_length=8192,  # Set reasonable max length
        hhem_score_threshold=0.5  # Default threshold
    )
    return scorer


def test_model_initialization(mock_model_setup):
    """Test model initialization with different configurations"""
    # Test CPU initialization
    scorer = HallucinationScorer(
        model_name_or_path=mock_model_setup,
        device="cpu"
    )
    assert scorer.device == "cpu"
    assert scorer.model_name_or_path == mock_model_setup
    
    # Test CUDA initialization (when available)
    if torch.cuda.is_available():
        scorer = HallucinationScorer(
            model_name_or_path=mock_model_setup,
            device="cuda"
        )
        assert scorer.device == "cuda"
    else:
        with pytest.raises(ValueError):
            HallucinationScorer(
                model_name_or_path=mock_model_setup,
                device="cuda"
            )
    
    # Test model download
    with patch("os.path.isdir", return_value=False):
        scorer = HallucinationScorer(
            model_name_or_path="wandb/hallucination_scorer",
            device="cpu"
        )
        assert scorer._local_model_path is not None


def test_model_weights_download(mock_model_setup):
    """Test model weights download functionality"""
    download_path = None
    
    def mock_download(*args, **kwargs):
        nonlocal download_path
        download_path = tempfile.mkdtemp()
        return download_path
    
    with patch("weave.scorers.llm_utils.download_model", mock_download):
        scorer = HallucinationScorer(
            model_name_or_path="wandb/hallucination_scorer",
            device="cpu"
        )
        assert scorer._local_model_path == download_path
        assert os.path.exists(download_path)


def test_model_loading_performance(mock_model_setup):
    """Test model loading performance and memory usage"""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    start_time = time.time()
    scorer = HallucinationScorer(
        model_name_or_path=mock_model_setup,
        device="cpu"
    )
    load_time = time.time() - start_time
    
    # Performance checks
    assert load_time < 30  # Model should load within 30 seconds
    
    # Memory usage check
    current_memory = process.memory_info().rss
    memory_increase = current_memory - initial_memory
    assert memory_increase < 2 * 1024 * 1024 * 1024  # Should use less than 2GB additional memory


@pytest.mark.asyncio
async def test_scoring_latency(hallucination_scorer):
    """Test scoring latency with different input sizes"""
    latencies = []
    
    for size in [100, 1000, 5000]:
        query = "What is this text about?"
        context, output = generate_context_and_output(size)
        
        start_time = time.time()
        result = await hallucination_scorer.score(
            query=query,
            context=context,
            output=output
        )
        latency = time.time() - start_time
        latencies.append(latency)
        
        # Basic result validation
        assert "flagged" in result
        assert "extras" in result
        assert "score" in result["extras"]
    
    # Latency should scale roughly linearly
    # The ratio between consecutive latencies should be less than the ratio of input sizes
    for i in range(1, len(latencies)):
        assert latencies[i] / latencies[i-1] < 10


@pytest.mark.asyncio
async def test_memory_usage_during_scoring(hallucination_scorer):
    """Test memory usage during scoring operations"""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    memory_measurements = []
    
    for size in [1000, 5000, 10000]:
        query = "What is this text about?"
        context, output = generate_context_and_output(size)
        
        _ = await hallucination_scorer.score(
            query=query,
            context=context,
            output=output
        )
        
        current_memory = process.memory_info().rss
        memory_measurements.append(current_memory - initial_memory)
        
    # Memory usage should not grow exponentially
    for i in range(1, len(memory_measurements)):
        ratio = memory_measurements[i] / max(memory_measurements[i-1], 1)
        assert ratio < 5  # Memory growth should be less than 5x between sizes


@pytest.mark.asyncio
async def test_resource_cleanup(hallucination_scorer):
    """Test proper cleanup of resources after scoring"""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    initial_handles = len(process.open_files())
    
    # Perform multiple scoring operations
    for _ in range(5):
        query = "What is this text about?"
        context, output = generate_context_and_output(1000)
        
        _ = await hallucination_scorer.score(
            query=query,
            context=context,
            output=output
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
            "expected_flagged": True
        },
        {
            "query": "What color is the sky?",
            "context": "The sky is blue.",
            "output": "The sky is blue.",
            "expected_flagged": False
        },
        {
            "query": "Describe the weather.",
            "context": "It's a sunny day with no clouds.",
            "output": "It's a sunny day.",
            "expected_flagged": False
        },
        {
            "query": "What did John eat?",
            "context": "John had a sandwich for lunch.",
            "output": "John had pizza for lunch.",
            "expected_flagged": True
        }
    ]
    
    for case in test_cases:
        result = await hallucination_scorer.score(
            query=case["query"],
            context=case["context"],
            output=case["output"]
        )
        assert result["flagged"] == case["expected_flagged"]
        assert isinstance(result["extras"]["score"], float)
        assert 0 <= result["extras"]["score"] <= 1


@pytest.mark.asyncio
async def test_integration_with_evaluation(hallucination_scorer):
    """Test integration with Weave's evaluation framework"""
    dataset = [
        {
            "query": "What color is the sky?",
            "context": "The sky is blue.",
            "output": "The sky appears blue due to Rayleigh scattering."
        },
        {
            "query": "What's the weather?",
            "context": "It's sunny with no clouds.",
            "output": "It's a clear, sunny day."
        }
    ]
    
    @weave.op
    def model(query, context):
        return "Generated response"
    
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_scorer]
    )
    
    result = await evaluation.evaluate(model)
    assert "HallucinationScorer" in result
    assert isinstance(result["HallucinationScorer"]["flagged"]["true_count"], int)


@pytest.mark.asyncio
async def test_large_input_handling(hallucination_scorer):
    """Test handling of large inputs"""
    query = "What is the story about?"
    context, output = generate_context_and_output(100_000, context_ratio=0.8)

    start_time = time.time()
    result = await hallucination_scorer.score(
        query=query,
        context=context,
        output=output
    )
    end_time = time.time()

    # Performance checks
    assert end_time - start_time < 60  # Should complete within 60 seconds
    assert "flagged" in result
    assert "extras" in result
    assert "score" in result["extras"]

    # Memory checks
    process = psutil.Process()
    memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
    assert memory_usage < 4096  # Should use less than 4GB RAM


def test_error_handling(hallucination_scorer):
    """Test error handling for various edge cases"""
    # Test empty inputs
    with pytest.raises(ValueError):
        hallucination_scorer.score(query="", context="", output="")
    
    # Test invalid device
    with pytest.raises(ValueError):
        HallucinationScorer(
            model_name_or_path="test",
            device="invalid_device"
        )
    
    # Test missing model path
    with pytest.raises(ValueError):
        HallucinationScorer(
            model_name_or_path="",
            device="cpu"
        )
    
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
        top_p=90  # Changed to integer
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
