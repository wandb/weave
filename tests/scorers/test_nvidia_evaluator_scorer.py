from unittest.mock import MagicMock

import pytest
import requests
from huggingface_hub import HfApi

import weave
from weave import Dataset, Evaluation
from weave.scorers.nvidia_evaluator_scorer import NvidiaNeMoEvaluatorScorer

# Testing the actual NvidiaNeMoEvaluatorScorer functionality is not possible
# since it requires a running instance of the NeMo Evaluator service.
# The tests below mock the service calls to verify the code paths.

NvidiaNeMoEvaluatorScorer._validate_services = lambda self: None

HfApi.__init__ = lambda self, *args, **kwargs: None
HfApi.create_repo = lambda self, *args, **kwargs: None
HfApi.upload_file = lambda self, *args, **kwargs: {"url": "http://fake-upload"}

# --- Fake responses for external API calls ---

class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        pass

def fake_post(url, headers=None, json=None, **kwargs):
    # This fake_post mimics the evaluator endpoint calls used in _write_job.
    if url.endswith("/v1/evaluation/jobs"):
        return FakeResponse({"id": "test-job"})
    return FakeResponse({})


def fake_get(url, headers=None, **kwargs):
    # This fake_get covers:
    # 1. Service validation (datastore and evaluator endpoints)
    # 2. Polling the job status in _wait_eval_job (always returning "completed")
    # 3. Getting job results.

    if url.endswith("/v1/datastore/namespaces"):
        return FakeResponse({})
    elif url.endswith("/v1/evaluation/jobs"):
        return FakeResponse({})
    # When polling the job status, return completed status.
    if "/v1/evaluation/jobs/test-job/results" in url:
        return FakeResponse({"tasks": {"coherence": 0.8}})
    return FakeResponse({"status": "completed", "status_details": {"progress": 100.0}})


# --- Patch the HuggingFace client so no real API calls happen ---
@pytest.fixture(autouse=True)
def patch_hfapi(monkeypatch):
    # Whenever a new HfApi is constructed, return a fake instance.
    fake_hf_instance = MagicMock()
    fake_hf_instance.create_repo.return_value = None
    fake_hf_instance.upload_file.return_value = {"url": "http://fake-upload"}
    monkeypatch.setattr(
        "huggingface_hub.HfApi", lambda *args, **kwargs: fake_hf_instance
    )


def test_score_with_both_inputs_fails(monkeypatch):
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)

    prompt_messages = [{"role": "user", "content": "Evaluate this: {output}"}]
    metrics = {"coherence": {"type": "float"}}
    scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace="temp-wv-ns",
        repo_name="weave-ds",
        judge_prompt_template=prompt_messages,
        judge_metrics=metrics,
        judge_url="https://integrate.api.nvidia.com/v1",
        judge_model_id="meta/llama-3.3-70b-instruct",
        judge_api_key="token",
    )
    dataset = weave.Dataset(rows=[{"output": "Sucks"}])
    with pytest.raises(
        ValueError, match="Only one of 'dataset' or 'output' can be provided."
    ):
        scorer.score(output="Test", dataset=dataset)


def test_score_without_judge_prompt_or_configuration(monkeypatch):
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    # Provide None for judge_prompt_template and judge_metrics without setting configuration_name
    scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace="temp-wv-ns",
        repo_name="weave-ds",
        judge_prompt_template=None,
        judge_metrics=None,
        judge_url="https://integrate.api.nvidia.com/v1",
        judge_model_id="meta/llama-3.3-70b-instruct",
        judge_api_key="token",
    )
    with pytest.raises(
        ValueError,
        match="You must provide either 'judge_prompt_template' or 'configuration_name'.",
    ):
        scorer.score(output="Test")


def test_score_without_judge_info(monkeypatch):
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    prompt_messages = [{"role": "user", "content": "Evaluate this: {output}"}]
    metrics = {"coherence": {"type": "float"}}
    scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace="temp-wv-ns",
        repo_name="weave-ds",
        judge_prompt_template=prompt_messages,
        judge_metrics=metrics,
        judge_url=None,
        judge_model_id=None,
        judge_api_key=None,
    )
    with pytest.raises(
        ValueError,
        match="You must provide either 'judge_url, judge_model_id, and judge_api_key' or 'target_name'.",
    ):
        scorer.score(output="Test")
