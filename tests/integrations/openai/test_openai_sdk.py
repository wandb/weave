from dataclasses import dataclass, field
from functools import partial
from unittest.mock import Mock

import pytest

import weave
from weave.integrations.openai.openai_sdk import (
    _normalize_openai_cache_tokens,
    create_wrapper_async,
    create_wrapper_sync,
    openai_on_finish,
    openai_on_input_handler,
    serverless_inference_call_display_name,
)
from weave.trace.autopatch import OpSettings
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter, CostCreateReq


@dataclass
class DummyClient:
    _base_url: str
    _version: str = "1.0.0"


@dataclass
class DummyCompletion:
    base_url: str
    version: str = "1.0.0"
    messages: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._client = DummyClient(self.base_url, self.version)


class NonCompletion:
    """An object that doesn't match completion_instance_check requirements."""

    def __init__(self):
        self.data = "not a completion"


def test_normalize_openai_responses_cache_tokens() -> None:
    usage = {
        "input_tokens": 100,
        "input_tokens_details": {
            "cached_tokens": 20,
            "cache_write_tokens": 30,
        },
        "output_tokens": 10,
        "total_tokens": 110,
    }

    _normalize_openai_cache_tokens(usage)

    assert usage == {
        "input_tokens": 100,
        "input_tokens_details": {
            "cached_tokens": 20,
            "cache_write_tokens": 30,
        },
        "output_tokens": 10,
        "total_tokens": 110,
        "cache_read_input_tokens": 20,
        "cache_creation_input_tokens": 30,
    }


def test_normalize_openai_chat_completions_cache_tokens() -> None:
    usage = {
        "prompt_tokens": 100,
        "prompt_tokens_details": {
            "cache_write_tokens": 30,
        },
        "completion_tokens": 10,
        "total_tokens": 110,
    }

    _normalize_openai_cache_tokens(usage)

    assert usage == {
        "prompt_tokens": 100,
        "prompt_tokens_details": {
            "cache_write_tokens": 30,
        },
        "completion_tokens": 10,
        "total_tokens": 110,
        "cache_creation_input_tokens": 30,
    }


@pytest.mark.parametrize(
    (
        "op_name",
        "input_tokens_key",
        "input_tokens_details_key",
        "output_tokens_key",
    ),
    [
        pytest.param(
            "openai.responses.create",
            "input_tokens",
            "input_tokens_details",
            "output_tokens",
            id="responses",
        ),
        pytest.param(
            "openai.chat.completions.create",
            "prompt_tokens",
            "prompt_tokens_details",
            "completion_tokens",
            id="chat-completions",
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "model",
        "cache_write_tokens",
        "cache_creation_input_token_cost",
    ),
    [
        pytest.param(
            "gpt-5.5-cache-write-repro",
            None,
            0.0,
            id="pre-5.6-no-write-field",
        ),
        pytest.param(
            "gpt-5.6-cache-write-repro",
            300_000,
            6.25e-6,
            id="gpt-5.6",
        ),
        pytest.param(
            "future-openai-cache-write-repro",
            300_000,
            6.25e-6,
            id="post-5.6-with-registry-rate",
        ),
    ],
)
def test_openai_cache_write_tokens_follow_model_pricing(
    client: WeaveClient,
    op_name: str,
    input_tokens_key: str,
    input_tokens_details_key: str,
    output_tokens_key: str,
    model: str,
    cache_write_tokens: int | None,
    cache_creation_input_token_cost: float,
) -> None:
    prompt_token_cost = 5e-6
    completion_token_cost = 30e-6
    cache_read_input_token_cost = 0.5e-6
    client.server.cost_create(
        CostCreateReq(
            project_id=client.project_id,
            costs={
                model: {
                    "prompt_token_cost": prompt_token_cost,
                    "completion_token_cost": completion_token_cost,
                    "cache_read_input_token_cost": cache_read_input_token_cost,
                    "cache_creation_input_token_cost": cache_creation_input_token_cost,
                    "provider_id": "openai",
                }
            },
        )
    )
    input_tokens = 1_000_000
    cached_tokens = 200_000
    output_tokens = 100_000
    input_tokens_details = {"cached_tokens": cached_tokens}
    if cache_write_tokens is not None:
        input_tokens_details["cache_write_tokens"] = cache_write_tokens
    response = {
        "id": f"resp_{model}",
        "model": model,
        "usage": {
            input_tokens_key: input_tokens,
            input_tokens_details_key: input_tokens_details,
            output_tokens_key: output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }

    @weave.op(name=op_name)
    def create_response() -> dict:
        return response

    create_response._set_on_finish_handler(openai_on_finish)
    assert create_response() == response

    call = next(iter(create_response.calls()))
    expected_usage = {
        "requests": 1,
        input_tokens_key: input_tokens,
        input_tokens_details_key: input_tokens_details,
        output_tokens_key: output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cache_read_input_tokens": cached_tokens,
    }
    if cache_write_tokens is not None:
        expected_usage["cache_creation_input_tokens"] = cache_write_tokens
    assert call.summary["usage"] == {model: expected_usage}

    priced_calls = list(
        client.get_calls(
            filter=CallsFilter(call_ids=[call.id]),
            include_costs=True,
        )
    )
    assert len(priced_calls) == 1
    cost = priced_calls[0].summary["weave"]["costs"][model]
    assert {
        "prompt_tokens": cost["prompt_tokens"],
        "completion_tokens": cost["completion_tokens"],
        "cache_read_input_tokens": cost["cache_read_input_tokens"],
        "cache_creation_input_tokens": cost["cache_creation_input_tokens"],
        "prompt_tokens_total_cost": cost["prompt_tokens_total_cost"],
        "completion_tokens_total_cost": cost["completion_tokens_total_cost"],
        "cache_read_input_tokens_total_cost": cost[
            "cache_read_input_tokens_total_cost"
        ],
        "cache_creation_input_tokens_total_cost": cost[
            "cache_creation_input_tokens_total_cost"
        ],
    } == {
        "prompt_tokens": input_tokens,
        "completion_tokens": output_tokens,
        "cache_read_input_tokens": cached_tokens,
        "cache_creation_input_tokens": cache_write_tokens or 0,
        "prompt_tokens_total_cost": pytest.approx(
            (input_tokens - cached_tokens - (cache_write_tokens or 0))
            * prompt_token_cost
        ),
        "completion_tokens_total_cost": pytest.approx(
            output_tokens * completion_token_cost
        ),
        "cache_read_input_tokens_total_cost": pytest.approx(
            cached_tokens * cache_read_input_token_cost
        ),
        "cache_creation_input_tokens_total_cost": pytest.approx(
            (cache_write_tokens or 0) * cache_creation_input_token_cost
        ),
    }


def test_serverless_inference_call_display_name():
    display_name = partial(
        serverless_inference_call_display_name, "openai.chat.completions.create"
    )

    # W&B's OpenAI-compatible endpoint should show the actual provider and model.
    call = Mock(
        inputs={
            "self": {"client": {"base_url": "https://api.inference.wandb.ai/v1/"}},
            "model": "google/gemma-4-31B-it",
        }
    )
    assert display_name(call) == "Serverless Inference: google/gemma-4-31B-it"

    # Missing model metadata still identifies Serverless Inference accurately.
    call.inputs = {
        "self": {"client": {"base_url": "https://api.inference.wandb.ai/v1"}}
    }
    assert display_name(call) == "Serverless Inference"

    # OpenAI and other compatible endpoints retain the integration's op label.
    call.inputs = {
        "self": {"client": {"base_url": "https://api.openai.com/v1/"}},
        "model": "gpt-5",
    }
    assert display_name(call) == "openai.chat.completions.create"

    call.inputs = {}
    assert display_name(call) == "openai.chat.completions.create"


def test_openai_on_input_handler_with_completion_instance():
    """Test that openai_on_input_handler processes completion instances correctly."""
    completion = DummyCompletion("https://api.openai.com", "1.2.3")
    mock_op = Mock()
    mock_op.name = "test_op"

    args = (completion, {"model": "gpt-4", "messages": []})
    kwargs = {"temperature": 0.7}

    result = openai_on_input_handler(mock_op, args, kwargs)

    # Should return ProcessedInputs
    assert result is not None
    assert hasattr(result, "inputs")
    assert hasattr(result, "args")
    assert hasattr(result, "kwargs")

    # Should have converted completion to dict in inputs
    assert "self" in result.inputs
    expected_self = {
        "client": {
            "base_url": "https://api.openai.com",
            "version": "1.2.3",
        }
    }
    assert result.inputs["self"] == expected_self

    # Args should be modified (completion converted to dict)
    assert result.args[0] == expected_self
    assert result.args[1] == {"model": "gpt-4", "messages": []}

    # Kwargs should remain unchanged
    assert result.kwargs == {"temperature": 0.7}


def test_openai_on_input_handler_with_non_completion_instance():
    """Test that openai_on_input_handler handles non-completion instances correctly."""
    mock_op = Mock()
    mock_op.name = "test_op"
    non_completion = NonCompletion()

    args = (non_completion, {"model": "gpt-4"})
    kwargs = {"temperature": 0.7}

    result = openai_on_input_handler(mock_op, args, kwargs)

    # Should still return ProcessedInputs
    assert result is not None
    assert hasattr(result, "inputs")

    # Should not have "self" in inputs since it's not a completion instance
    assert "self" not in result.inputs

    # Args should remain unchanged
    assert result.args == args


def test_openai_on_input_handler_with_easy_prompt():
    """Test that openai_on_input_handler handles EasyPrompt correctly."""
    completion = DummyCompletion("https://api.openai.com")
    mock_op = Mock()
    mock_op.name = "test_op"

    # Create a real EasyPrompt instance
    easy_prompt = weave.EasyPrompt(
        messages=[{"role": "user", "content": "Hello"}], model="gpt-4"
    )

    args = (completion, easy_prompt)
    kwargs = {"temperature": 0.5}

    result = openai_on_input_handler(mock_op, args, kwargs)

    # Should return ProcessedInputs
    assert result is not None

    # Should have both "self" and "prompt" in inputs
    assert "self" in result.inputs
    assert "prompt" in result.inputs
    assert result.inputs["prompt"] == easy_prompt

    # Args should be modified (completion converted, prompt removed)
    assert len(result.args) == 1
    expected_self = {
        "client": {
            "base_url": "https://api.openai.com",
            "version": "1.0.0",
        }
    }
    assert result.args[0] == expected_self

    # Kwargs should be updated with prompt data
    assert "messages" in result.kwargs
    assert "model" in result.kwargs
    assert result.kwargs["temperature"] == 0.5
    assert result.kwargs["messages"] == [{"role": "user", "content": "Hello"}]
    assert result.kwargs["model"] == "gpt-4"


def test_openai_on_input_handler_preserves_original_args_kwargs():
    """Test that openai_on_input_handler preserves original args and kwargs."""
    completion = DummyCompletion("https://api.mistral.ai", "0.9.0")
    mock_op = Mock()
    mock_op.name = "test_op"

    original_args = (completion, {"model": "mistral-7b"})
    original_kwargs = {"max_tokens": 100}

    result = openai_on_input_handler(mock_op, original_args, original_kwargs)

    # Should preserve original values
    assert result.original_args == original_args
    assert result.original_kwargs == original_kwargs


def test_openai_on_input_handler_with_no_args():
    """Test openai_on_input_handler behavior with no arguments."""
    mock_op = Mock()
    mock_op.name = "test_op"

    result = openai_on_input_handler(mock_op, (), {})

    assert result is not None
    assert result.args == ()
    assert result.kwargs == {}
    assert "self" not in result.inputs


def test_stream_options_injected_for_openai_base_url_sync() -> None:
    captured = {}

    def dummy_fn(completion, **kwargs):
        captured.update(kwargs)
        return "ok"

    wrapped = create_wrapper_sync(OpSettings())(dummy_fn)

    wrapped(DummyCompletion("https://api.openai.com"), stream=True)

    assert captured.get("stream_options") == {"include_usage": True}


def test_stream_options_not_injected_for_non_openai_base_url_sync() -> None:
    captured = {}

    def dummy_fn(completion, **kwargs):
        captured.update(kwargs)
        return "ok"

    wrapped = create_wrapper_sync(OpSettings())(dummy_fn)

    wrapped(DummyCompletion("https://api.mistral.ai"), stream=True)

    assert "stream_options" not in captured


@pytest.mark.asyncio
async def test_stream_options_injected_for_openai_base_url_async() -> None:
    captured = {}

    async def dummy_fn(completion, **kwargs):
        captured.update(kwargs)
        return "ok"

    wrapped = create_wrapper_async(OpSettings())(dummy_fn)

    await wrapped(DummyCompletion("https://api.openai.com"), stream=True)

    assert captured.get("stream_options") == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_options_not_injected_for_non_openai_base_url_async() -> None:
    captured = {}

    async def dummy_fn(completion, **kwargs):
        captured.update(kwargs)
        return "ok"

    wrapped = create_wrapper_async(OpSettings())(dummy_fn)

    await wrapped(DummyCompletion("https://api.mistral.ai"), stream=True)

    assert "stream_options" not in captured
