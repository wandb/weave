from unittest.mock import MagicMock

import pytest
import requests

import weave
from weave import Dataset, Evaluation
from weave.scorers.nvidia_evaluator_scorer import NvidiaNeMoEvaluatorScorer

# --- Fake responses for external API calls ---


def fake_post(url, headers=None, json=None, **kwargs):
    # This fake_post mimics the evaluator endpoint calls used in _write_job.
    class FakeResponse:
        def __init__(self, json_data):
            self._json = json_data

        def json(self):
            return self._json

        def raise_for_status(self):
            pass

    if url.endswith("/v1/evaluation/configs"):
        return FakeResponse({})
    elif url.endswith("/v1/evaluation/targets"):
        return FakeResponse({})
    elif url.endswith("/v1/evaluation/jobs"):
        return FakeResponse({"id": "test-job"})
    return FakeResponse({})


def fake_get(url, headers=None, **kwargs):
    # This fake_get covers:
    # 1. Service validation (datastore and evaluator endpoints)
    # 2. Polling the job status in _wait_eval_job (always returning "completed")
    # 3. Getting job results.
    class FakeResponse:
        def __init__(self, json_data):
            self._json = json_data

        def json(self):
            return self._json

        def raise_for_status(self):
            pass

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


# --- Define the "op" functions to be tested ---


def run_scorer():
    """
    A synchronous op that instantiates NvidiaNeMoEvaluatorScorer with fixed parameters,
    scores a single output string, and returns the result.
    """
    prompt_messages = [{"role": "user", "content": "Evaluate this: {output}"}]
    metrics = {"coherence": {"type": "float"}}

    nemo_eval_scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace="temp-wv-ns",
        repo_name="weave-ds",
        judge_prompt_template=prompt_messages,
        judge_metrics=metrics,
        judge_url="https://integrate.api.nvidia.com/v1",
        judge_model_id="meta/llama-3.3-70b-instruct",
        judge_api_key="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",
    )
    output = "This movie truly sucked"
    return nemo_eval_scorer.score(output=output)


@pytest.mark.parametrize("op_func", [run_scorer])
def test_run_scorer(op_func, monkeypatch):
    # Patch requests so that no actual HTTP calls are made.
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    score = op_func()
    assert score == {"coherence": 0.8}


# Define the asynchronous op.
@pytest.mark.asyncio
async def run_evaluation():
    """
    An asynchronous op that instantiates NvidiaNeMoEvaluatorScorer,
    builds a small dataset, and uses it in a dummy Evaluation.
    """
    prompt_messages = [{"role": "user", "content": "Evaluate this: {output}"}]
    metrics = {"coherence": {"type": "float"}}

    nemo_eval_scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace="temp-wv-ns",
        repo_name="weave-ds",
        judge_prompt_template=prompt_messages,
        judge_metrics=metrics,
        judge_url="https://integrate.api.nvidia.com/v1",
        judge_model_id="meta/llama-3.3-70b-instruct",
        judge_api_key="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",
    )
    dataset = Dataset(
        rows=[{"output": "This movie truly sucked"}, {"output": "This movie was great"}]
    )

    # Define a dummy FakeModel with a predict method.

    class FakeModel(weave.Model):
        @weave.op()
        def predict(self, output):
            pass

    evaluation = Evaluation(dataset=dataset, scorers=[nemo_eval_scorer])
    results = await evaluation.evaluate(FakeModel())
    return results


@pytest.mark.asyncio
async def test_run_evaluation(monkeypatch):
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "get", fake_get)
    results = await run_evaluation()
    assert results.get("NvidiaNeMoEvaluatorScorer", {}).get("coherence") == 1.6


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


def test_run_scorer_with_10_data_points(monkeypatch):
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
    dataset = Dataset(rows=[{"output": f"Test output {i}"} for i in range(10)])
    result = scorer.score(dataset=dataset)
    # Since our fake GET always returns {"tasks": {"coherence": 0.8}},
    # we expect the scoreboard to be exactly that.
    assert isinstance(result, dict)
    assert "coherence" in result
    assert isinstance(result["coherence"], float)
