"""
Test that the scorer unification works as expected. Specifically, that the same scorer can:
1. Be constructed locally
2. Be ran locally
3. Be constructed remotely (and result in the same digest as #1)
4. Be ran remotely
5. Be fetched from remote and ran locally
"""

import os
from contextlib import contextmanager

import pytest

import weave
from weave.scorers.test_scorer import TestScorer
from weave.trace.weave_client import CallRef, WeaveClient, get_ref
from weave.trace_server.trace_server_interface import CallsQueryReq


@contextmanager
def temp_env(key: str, value: str):
    old_value = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old_value is None:
            del os.environ[key]
        else:
            os.environ[key] = old_value


def make_dataset():
    return [{"a": 1, "b": "hello"}]


def make_model():
    @weave.op
    def model(a: int, b: str) -> str:
        return str(a) + ":" + b

    return model


def execute_test_call():
    model = make_model()
    rows = make_dataset()
    res, call = model.call(*rows[0].values())
    assert call.inputs == {"a": 1, "b": "hello"}

    return res, call


def assert_valid_results(client, scorer):
    exp_score = {
        "input_a": 1,
        "input_b_length": 5,
        "output_length": 7,
        "scorer_property": 42,
        "test_api_key_length": 5,
    }
    calls = client.server.calls_query(
        CallsQueryReq(project_id=client._project_id(), include_feedback=True)
    ).calls
    assert len(calls) >= 2
    model_call = [c for c in calls if "model" in c.op_name][0]
    score_call = [c for c in calls if "TestScorer" in c.op_name][0]
    feedback_entry = model_call.summary["weave"]["feedback"][0]
    feedback_entry["feedback_type"] = "wandb.runnable.TestScorer"
    feedback_entry["payload"] = {"output": exp_score}
    feedback_entry["runnable_ref"] = scorer.ref.uri()
    project_id = client._project_id()
    entity, project = project_id.split("/")
    feedback_entry["call_ref"] = CallRef(
        entity=entity,
        project=project,
        id=score_call.id,
    ).uri()

    assert score_call.output == exp_score


def create_local_test_scorer():
    return TestScorer(scorer_property=42)


def test_manual_scoring_local_construction(client: WeaveClient):
    res, call = execute_test_call()

    # 1. Local Construction
    scorer = create_local_test_scorer()

    # 2. Manual Scoring
    with temp_env("TEST_API_KEY", "12345"):
        score, score_call = scorer.score.call(
            self=scorer, a=call.inputs["a"], b=call.inputs["b"], output=res
        )

    # 3. Manual Linking
    client._send_score_call(
        call, score_call, scorer_object_ref_uri=get_ref(scorer).uri()
    )

    # Verify Correct Results
    assert_valid_results(client, scorer)


def test_client_scoring_local_construction(client: WeaveClient):
    res, call = execute_test_call()

    # 1. Local Construction
    scorer = create_local_test_scorer()

    # 2. Client Scoring
    with temp_env("TEST_API_KEY", "12345"):
        score, score_call = call._apply_scorer(scorer)

    # Verify Correct Results
    assert_valid_results(client, scorer)


@pytest.mark.asyncio
async def test_evaluation_scoring_local_construction(client: WeaveClient):
    model = make_model()
    scorer = create_local_test_scorer()
    rows = make_dataset()
    eval = weave.Evaluation(dataset=rows, scorers=[scorer])
    with temp_env("TEST_API_KEY", "12345"):
        await eval.evaluate(model)

    assert_valid_results(client, scorer)


def test_remote_scoring_local_construction(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_manual_scoring_remote_construction(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_client_scoring_remote_construction(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_evaluation_scoring_remote_construction(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_remote_scoring_remote_construction(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_local_remote_construction_identity(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_support_for_field_mapping(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_support_for_generic_parameters(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_support_for_labelled_examples(client: WeaveClient):
    raise NotImplementedError("Not implemented")


def test_support_for_context_fields(client: WeaveClient):
    raise NotImplementedError("Not implemented")
