from __future__ import annotations

import os
from typing import Any

import pytest
import verifiers as vf
from datasets import Dataset
from openai import OpenAI

from weave.integrations.integration_utilities import (
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
def test_verifiers_environment_evaluate_with_mock_env(client: WeaveClient) -> None:
    """Run verifiers evaluation with a mocked environment and assert patched ops.

    This test avoids external dependencies and focuses purely on the Weave
    patching applied in `weave.integrations.verifiers.verifiers`.
    """

    class MockEnv(vf.MultiTurnEnv):
        """Simple multi-turn environment that completes in one assistant turn.

        The rubric includes two reward functions:
        - ThinkParser.format_reward (wrapped by the integration)
        - A custom reward that calls parser.parse to exercise that wrapper
        """

        def __init__(self) -> None:
            dataset = Dataset.from_dict(
                {
                    "question": ["What is 1+1?"],
                    "answer": ["2"],
                }
            )
            super().__init__(
                dataset=dataset,
                eval_dataset=None,
                message_type="chat",
                max_workers=2,
                parser=vf.ThinkParser(),
                rubric=vf.Rubric(),
            )
            # Add a format reward from the parser (this will be wrapped)
            self.rubric.add_reward_func(self.parser.get_format_reward_func())

            # Add a reward that explicitly calls parser.parse (also wrapped)
            def _parse_reward(
                completion: list[vf.ChatMessage], *, parser: vf.Parser, **_: Any
            ) -> float:
                """Invoke parser.parse on assistant messages and return 1.0.

                Args:
                    completion: Conversation messages.
                    parser: Injected parser instance from rubric.

                Returns:
                    1.0 always.

                Examples:
                    >>> from verifiers.parsers.think_parser import ThinkParser
                    >>> parser = ThinkParser()
                    >>> _ = _parse_reward([{ 'role': 'assistant', 'content': 'hi'}], parser=parser)
                """
                for m in completion:
                    if m.get("role") == "assistant":
                        parser.parse(m["content"])
                return 1.0

            self.rubric.add_reward_func(_parse_reward)

        async def is_completed(self, messages, state, **kwargs):  # type: ignore[no-untyped-def]
            return state["turn"] >= 1

        async def env_response(self, messages, state, **kwargs):  # type: ignore[no-untyped-def]
            return [], state

    env = MockEnv()

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "DUMMY_API_KEY"))
    results = env.evaluate(
        openai_client,
        "gpt-4.1-mini",
        num_examples=1,
        rollouts_per_example=1,
        max_concurrent=8,
    )

    assert results is not None
    assert len(results.prompt) == 1

    # Validate that the expected weave ops were traced
    calls = list(client.get_calls())
    flattened = flatten_calls(calls)
    assert len(flattened) == 43

    assert flattened_calls_to_names(flattened) == [
        ("verifiers.Environment.evaluate", 0),
        ("verifiers.Environment.generate", 1),
        ("verifiers.Environment.a_generate", 2),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 3),
        ("verifiers.Environment.get_model_response", 4),
        ("verifiers.Rubric.score_rollouts", 3),
        ("verifiers.Rubric.score_rollout", 4),
        ("verifiers.ThinkParser.format_reward", 5),
        ("verifiers.Parser.parse", 5),
        ("verifiers.Parser.extract_fn", 6),
        ("verifiers.Environment.generate", 0),
        ("verifiers.Environment.a_generate", 1),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 2),
        ("verifiers.Environment.get_model_response", 3),
        ("verifiers.Rubric.score_rollouts", 2),
        ("verifiers.Rubric.score_rollout", 3),
        ("verifiers.ThinkParser.format_reward", 4),
        ("verifiers.Parser.parse", 4),
        ("verifiers.Parser.extract_fn", 5),
        ("verifiers.Environment.a_generate", 0),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 1),
        ("verifiers.Environment.get_model_response", 2),
        ("verifiers.Rubric.score_rollouts", 1),
        ("verifiers.Rubric.score_rollout", 2),
        ("verifiers.ThinkParser.format_reward", 3),
        ("verifiers.Parser.parse", 3),
        ("verifiers.Parser.extract_fn", 4),
        ("verifiers.envs.multiturn_env.MultiTurnEnv.rollout", 0),
        ("verifiers.Environment.get_model_response", 1),
        ("verifiers.Environment.get_model_response", 0),
        ("verifiers.Rubric.score_rollouts", 0),
        ("verifiers.Rubric.score_rollout", 1),
        ("verifiers.ThinkParser.format_reward", 2),
        ("verifiers.Parser.parse", 2),
        ("verifiers.Parser.extract_fn", 3),
        ("verifiers.Rubric.score_rollout", 0),
        ("verifiers.ThinkParser.format_reward", 1),
        ("verifiers.Parser.parse", 1),
        ("verifiers.Parser.extract_fn", 2),
        ("verifiers.ThinkParser.format_reward", 0),
        ("verifiers.Parser.parse", 0),
        ("verifiers.Parser.extract_fn", 1),
        ("verifiers.Parser.extract_fn", 0),
    ]

    call_0, _ = flattened[0]
    assert op_name_from_ref(call_0.op_name) == "verifiers.Environment.evaluate"
    assert call_0.started_at < call_0.ended_at
