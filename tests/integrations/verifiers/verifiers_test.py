from __future__ import annotations

import os
import subprocess

import pytest
import verifiers as vf
from openai import OpenAI

from weave.integrations.integration_utilities import (
    filter_body,
    flatten_calls,
    flattened_calls_to_names,
    op_name_from_ref,
)
from weave.integrations.verifiers.verifiers import get_verifiers_patcher
from weave.trace.weave_client import WeaveClient


@pytest.fixture(autouse=True)
def patch_verifiers() -> None:
    """Patch Verifiers for all tests in this file."""
    patcher = get_verifiers_patcher()
    patcher.attempt_patch()
    try:
        yield
    finally:
        patcher.undo_patch()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_verifiers_environment_evaluate(client: WeaveClient) -> None:
    """Run a real verifiers environment evaluation and assert trace timeline.

    We avoid external network calls by stubbing only the LLM response method on the
    environment instance, while exercising the real verifiers evaluation flow.
    """
    # Ensure the gsm8k environment is available in CI by invoking the CLI installer
    subprocess.run(["vf-install", "gsm8k", "--from-repo"], check=True)

    env = vf.load_environment("gsm8k")

    # Test with a model
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    results = env.evaluate(
        openai_client,
        "gpt-4.1-mini",
        num_examples=1,
        rollouts_per_example=2,
        max_concurrent=32,
    )

    assert results is not None

    calls = list(client.get_calls())
    flattened = flatten_calls(calls)
    assert len(flattened) == 62
    assert flattened_calls_to_names(flattened) == [
        ("verifiers.Environment.evaluate", 0),
        ("verifiers.Environment.generate", 1),
        ("verifiers.Environment.a_generate", 2),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 3),
        ("verifiers.Environment.get_model_response", 4),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 3),
        ("verifiers.Environment.get_model_response", 4),
        ("verifiers.Rubric.score_rollouts", 3),
        ("verifiers.Rubric.score_rollout", 4),
        ("verifiers.ThinkParser.parse", 5),
        ("verifiers.ThinkParser.format_reward", 5),
        ("verifiers.Rubric.score_rollout", 4),
        ("verifiers.ThinkParser.parse", 5),
        ("verifiers.ThinkParser.format_reward", 5),
        ("verifiers.Environment.generate", 0),
        ("verifiers.Environment.a_generate", 1),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 2),
        ("verifiers.Environment.get_model_response", 3),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 2),
        ("verifiers.Environment.get_model_response", 3),
        ("verifiers.Rubric.score_rollouts", 2),
        ("verifiers.Rubric.score_rollout", 3),
        ("verifiers.ThinkParser.parse", 4),
        ("verifiers.ThinkParser.format_reward", 4),
        ("verifiers.Rubric.score_rollout", 3),
        ("verifiers.ThinkParser.parse", 4),
        ("verifiers.ThinkParser.format_reward", 4),
        ("verifiers.Environment.a_generate", 0),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 1),
        ("verifiers.Environment.get_model_response", 2),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 1),
        ("verifiers.Environment.get_model_response", 2),
        ("verifiers.Rubric.score_rollouts", 1),
        ("verifiers.Rubric.score_rollout", 2),
        ("verifiers.ThinkParser.parse", 3),
        ("verifiers.ThinkParser.format_reward", 3),
        ("verifiers.Rubric.score_rollout", 2),
        ("verifiers.ThinkParser.parse", 3),
        ("verifiers.ThinkParser.format_reward", 3),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 0),
        ("verifiers.Environment.get_model_response", 1),
        ("verifiers.Environment.get_model_response", 0),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 0),
        ("verifiers.Environment.get_model_response", 1),
        ("verifiers.Environment.get_model_response", 0),
        ("verifiers.Rubric.score_rollouts", 0),
        ("verifiers.Rubric.score_rollout", 1),
        ("verifiers.ThinkParser.parse", 2),
        ("verifiers.ThinkParser.format_reward", 2),
        ("verifiers.Rubric.score_rollout", 1),
        ("verifiers.ThinkParser.parse", 2),
        ("verifiers.ThinkParser.format_reward", 2),
        ("verifiers.Rubric.score_rollout", 0),
        ("verifiers.ThinkParser.parse", 1),
        ("verifiers.ThinkParser.format_reward", 1),
        ("verifiers.Rubric.score_rollout", 0),
        ("verifiers.ThinkParser.parse", 1),
        ("verifiers.ThinkParser.format_reward", 1),
        ("verifiers.ThinkParser.parse", 0),
        ("verifiers.ThinkParser.format_reward", 0),
        ("verifiers.ThinkParser.parse", 0),
        ("verifiers.ThinkParser.format_reward", 0),
    ]

    call_0, _ = flattened[0]
    assert op_name_from_ref(call_0.op_name) == "verifiers.Environment.evaluate"
    assert call_0.started_at < call_0.ended_at
