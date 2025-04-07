"""Tests for the NVIDIA NeMo Evaluator Scorer."""

import pytest
from unittest.mock import Mock, patch
import requests
import weave
from weave.scorers.nvidia_evaluator_scorer import NvidiaNeMoEvaluatorScorer

@pytest.fixture
def mock_responses():
    """Fixture to provide mock API responses."""
    return {
        "service_check": {"reachable": True},
        "job_creation": {"id": "test-job-123"},
        "job_status": {
            "status": "completed",
            "status_details": {"progress": 100.0}
        },
        "job_results": {
            "tasks": {
                "llm-as-a-judge": {
                    "metrics": {
                        "relevance": {"mean": 0.85},
                        "coherence": {"mean": 0.92}
                    }
                }
            }
        }
    }

@pytest.fixture
def mock_requests(monkeypatch):
    """Fixture to mock requests.get and requests.post."""
    def mock_get(*args, **kwargs):
        mock_response = Mock()
        mock_response.json.return_value = {"reachable": True}
        mock_response.raise_for_status.return_value = None
        return mock_response

    def mock_post(*args, **kwargs):
        mock_response = Mock()
        mock_response.json.return_value = {"id": "test-job-123"}
        mock_response.raise_for_status.return_value = None
        return mock_response

    monkeypatch.setattr(requests, 'get', mock_get)
    monkeypatch.setattr(requests, 'post', mock_post)

@pytest.fixture
def nemo_evaluator_scorer(mock_requests):
    """Fixture that returns a NvidiaNeMoEvaluatorScorer instance with test configuration."""
    scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://test-evaluator.com",
        datastore_url="http://test-datastore.com",
        namespace="test-namespace",
        repo_name="test-repo",
        evaluator_token="test-token",
        datastore_token="test-token",
        judge_prompt_template=[{"role": "user", "content": "Evaluate this: {output}"}],
        judge_metrics={"relevance": {"type": "float"}, "coherence": {"type": "float"}},
        judge_url="http://test-judge.com",
        judge_model_id="test-model",
        judge_api_key="test-key"
    )
    return scorer

@pytest.fixture
def test_dataset():
    """Fixture that returns a test dataset."""
    return weave.Dataset(rows=[
        {"output": "Test output 1"},
        {"output": "Test output 2"}
    ])

@patch('requests.get')
@patch('requests.post')
@patch('huggingface_hub.HfApi')
def test_single_output_scoring(mock_hf_api, mock_post, mock_get, nemo_evaluator_scorer, mock_responses):
    """Test scoring a single output string."""
    # Configure mocks
    mock_get.side_effect = [
        Mock(json=lambda: mock_responses["service_check"]),
        Mock(json=lambda: mock_responses["service_check"]),
        Mock(json=lambda: mock_responses["job_status"]),
        Mock(json=lambda: mock_responses["job_results"])
    ]
    mock_post.return_value = Mock(json=lambda: mock_responses["job_creation"])
    mock_hf_api.return_value = Mock()
    
    # Test scoring
    result = nemo_evaluator_scorer.score(output="This is a test output")
    
    # Verify results
    assert "llm-as-a-judge" in result
    assert result["llm-as-a-judge"]["metrics"]["relevance"]["mean"] == 0.85
    assert result["llm-as-a-judge"]["metrics"]["coherence"]["mean"] == 0.92

@patch('requests.get')
@patch('requests.post')
@patch('huggingface_hub.HfApi')
def test_dataset_scoring(mock_hf_api, mock_post, mock_get, nemo_evaluator_scorer, mock_responses, test_dataset):
    """Test scoring a dataset with multiple outputs."""
    # Configure mocks
    mock_get.side_effect = [
        Mock(json=lambda: mock_responses["service_check"]),
        Mock(json=lambda: mock_responses["service_check"]),
        Mock(json=lambda: mock_responses["job_status"]),
        Mock(json=lambda: mock_responses["job_results"])
    ]
    mock_post.return_value = Mock(json=lambda: mock_responses["job_creation"])
    mock_hf_api.return_value = Mock()
    
    # Test scoring
    result = nemo_evaluator_scorer.score(dataset=test_dataset)
    
    # Verify results
    assert "llm-as-a-judge" in result
    assert isinstance(result["llm-as-a-judge"]["metrics"]["relevance"]["mean"], float)
    assert isinstance(result["llm-as-a-judge"]["metrics"]["coherence"]["mean"], float)

@patch('requests.get')
@patch('requests.post')
@patch('huggingface_hub.HfApi')
def test_service_validation_failure(mock_hf_api, mock_post, mock_get, mock_responses):
    """Test handling of service validation failures."""
    # Configure mock to simulate service failure
    mock_get.side_effect = requests.RequestException("Service unavailable")
    mock_hf_api.return_value = Mock()
    
    # Test service validation
    with pytest.raises(RuntimeError) as exc_info:
        scorer = NvidiaNeMoEvaluatorScorer(
            evaluator_url="http://test-evaluator.com",
            datastore_url="http://test-datastore.com",
            namespace="test-namespace",
            repo_name="test-repo",
            evaluator_token="test-token",
            datastore_token="test-token",
            judge_prompt_template=[{"role": "user", "content": "Evaluate this: {output}"}],
            judge_metrics={"relevance": {"type": "float"}, "coherence": {"type": "float"}},
            judge_url="http://test-judge.com",
            judge_model_id="test-model",
            judge_api_key="test-key"
        )
    
    assert "Service validation failed" in str(exc_info.value)
