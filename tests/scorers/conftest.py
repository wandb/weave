"""Shared test fixtures and utilities for scorer tests."""
import pytest
from unittest.mock import MagicMock
import time
import psutil
import os
from typing import Any, Callable, Dict, NamedTuple
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    latency: float  # seconds
    memory_used: float  # MB
    memory_peak: float  # MB
    cpu_percent: float  # percentage

# Common mock responses for different scorer types
@pytest.fixture
def mock_responses():
    return {
        "coherent": {
            "coherence": 0.9,
            "coherent": True,
            "flagged": False,
            "coherence_label": "coherent"
        },
        "incoherent": {
            "coherence": 0.2,
            "coherent": False,
            "flagged": True,
            "coherence_label": "incoherent"
        },
        "relevant": {
            "relevance": 0.9,
            "relevant": True,
            "flagged": False,
            "relevance_label": "relevant"
        },
        "irrelevant": {
            "relevance": 0.2,
            "relevant": False,
            "flagged": True,
            "relevance_label": "irrelevant"
        }
    }

@pytest.fixture
def mock_wandb(monkeypatch):
    """Mock wandb login and project."""
    monkeypatch.setattr("wandb.login", lambda *args, **kwargs: True)
    mock_project = MagicMock()
    monkeypatch.setattr("wandb.Api", lambda: MagicMock(project=lambda *args: mock_project))
    return mock_project

@pytest.fixture
def mock_model_loading(monkeypatch):
    """Mock model loading functions."""
    monkeypatch.setattr("weave.scorers.llm_utils.download_model", lambda *args, **kwargs: None)
    monkeypatch.setattr("weave.scorers.llm_utils.set_device", lambda *args: "cpu")
    monkeypatch.setattr("weave.scorers.llm_utils.get_model_path", lambda *args: "mock_path")

@pytest.fixture
def latency_threshold():
    """Maximum allowed latency in seconds for scorer operations."""
    return 30.0

@pytest.fixture
def measure_performance():
    """Fixture to measure and assert performance metrics of operations."""
    def _measure(
        operation: Callable,
        *args,
        latency_threshold: float = 30.0,
        memory_threshold_mb: float = 1024.0,  # 1GB
        **kwargs
    ) -> tuple[Any, PerformanceMetrics]:
        process = psutil.Process(os.getpid())
        
        # Get initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # Convert to MB
        peak_memory = initial_memory
        
        # Start monitoring
        start_time = time.time()
        start_cpu_percent = process.cpu_percent()
        
        # Run the operation
        result = operation(*args, **kwargs)
        
        # Measure final metrics
        end_time = time.time()
        end_memory = process.memory_info().rss / 1024 / 1024
        end_cpu_percent = process.cpu_percent()
        
        # Calculate metrics
        elapsed_time = end_time - start_time
        memory_used = end_memory - initial_memory
        peak_memory = max(initial_memory, end_memory)
        avg_cpu_percent = (start_cpu_percent + end_cpu_percent) / 2
        
        metrics = PerformanceMetrics(
            latency=elapsed_time,
            memory_used=memory_used,
            memory_peak=peak_memory,
            cpu_percent=avg_cpu_percent
        )
        
        # Assert performance requirements
        assert elapsed_time < latency_threshold, (
            f"Operation took {elapsed_time:.2f} seconds, "
            f"which exceeds the threshold of {latency_threshold:.2f} seconds"
        )
        
        assert memory_used < memory_threshold_mb, (
            f"Operation used {memory_used:.1f}MB of memory, "
            f"which exceeds the threshold of {memory_threshold_mb:.1f}MB"
        )
        
        return result, metrics
    
    return _measure

@pytest.fixture
def test_cases():
    """Common test cases for scorers."""
    return {
        "short": {
            "input": "What is the capital of France?",
            "output": "Paris is the capital of France.",
            "context": "France is a country in Europe.",
            "expected_score_range": (0.0, 1.0)
        },
        "medium": {
            "input": "Explain the theory of relativity.",
            "output": "Einstein's theory of relativity describes how the force of gravity arises from the curvature of spacetime caused by mass and energy.",
            "context": "Albert Einstein revolutionized physics with his theories of special and general relativity.",
            "expected_score_range": (0.0, 1.0)
        },
        "long": {
            "input": "Write a detailed analysis of climate change.",
            "output": "Climate change is a complex global phenomenon..." + " More text." * 100,
            "context": "Global warming is affecting ecosystems..." + " More context." * 100,
            "expected_score_range": (0.0, 1.0)
        },
        "edge_cases": {
            "empty": {"input": "", "output": "", "context": ""},
            "whitespace": {"input": "   ", "output": "\n\t ", "context": " \n "},
            "special_chars": {"input": "!@#$%^&*()", "output": "{}[]<>?", "context": "~`-_=+"},
            "unicode": {"input": "こんにちは", "output": "Café", "context": "über"},
        }
    }

@pytest.fixture
def mock_pipeline_factory(mock_responses):
    """Factory for creating mock pipelines with customizable behavior."""
    def create_mock_pipeline(scorer_type: str = "coherence"):
        def mock_pipeline(*args, **kwargs):
            def inner(text: str, **kwargs) -> list[dict]:
                # Default to positive case
                response = mock_responses[f"{scorer_type}"]
                
                # Check for negative indicators in text
                negative_indicators = {
                    "coherence": ["incoherent", "random", "hamburger pencil dance"],
                    "relevance": ["irrelevant", "moon", "unrelated"],
                }
                
                if any(ind in text.lower() for ind in negative_indicators.get(scorer_type, [])):
                    response = mock_responses[f"in{scorer_type}"]
                
                return [{"generated_text": str(response)}]
            return inner
        return mock_pipeline
    return create_mock_pipeline