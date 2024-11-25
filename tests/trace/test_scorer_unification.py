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

import weave
from weave.scorers.test_scorer import TestScorer
from weave.trace.weave_client import WeaveClient, get_ref
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


def execute_test_call():
    @weave.op
    def action(a: int, b: str) -> str:
        return str(a) + ":" + b

    res, call = action.call(1, "hello")
    assert call.inputs == {"a": 1, "b": "hello"}

    return res, call


def assert_valid_results(client, score, scorer, score_call):
    assert score == {
        "input_a": 1,
        "input_b_length": 5,
        "output_length": 7,
        "scorer_property": 42 * 1,
        "test_api_key_length": 5,
    }

    calls = client.server.calls_query(
        CallsQueryReq(project_id=client._project_id(), include_feedback=True)
    ).calls
    assert len(calls) == 2
    feedback_entry = calls[0].summary["weave"]["feedback"][0]
    feedback_entry["feedback_type"] = "wandb.runnable.TestScorer"
    feedback_entry["payload"] = {
        "output": {
            "input_a": 1,
            "input_b_length": 5,
            "output_length": 7,
            "scorer_property": 42,
            "test_api_key_length": 5,
        }
    }
    feedback_entry["runnable_ref"] = scorer.ref.uri()
    feedback_entry["call_ref"] = score_call.ref.uri()


def test_manual_scoring(client):
    res, call = execute_test_call()

    # 1. Manual Construction
    scorer = TestScorer(scorer_property=42)

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
    assert_valid_results(client, score, scorer, score_call)


def test_client_scoring(client: WeaveClient):
    res, call = execute_test_call()

    # 1. Manual Construction
    scorer = TestScorer(scorer_property=42)

    # 2. Client Scoring
    with temp_env("TEST_API_KEY", "12345"):
        score, score_call = call._apply_scorer(scorer)

    # Verify Correct Results
    assert_valid_results(client, score, scorer, score_call)
