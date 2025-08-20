from unittest.mock import Mock

import pytest

import weave
from weave.integrations.openai.openai_sdk import (
    create_wrapper_async,
    create_wrapper_sync,
    openai_on_input_handler,
)
from weave.trace.autopatch import OpSettings


class DummyClient:
    def __init__(self, base_url: str, version: str = "1.0.0"):
        self._base_url = base_url
        self._version = version


class DummyCompletion:
    def __init__(self, base_url: str, version: str = "1.0.0"):
        self._client = DummyClient(base_url, version)
        self.messages = []


class NonCompletion:
    """An object that doesn't match completion_instance_check requirements"""

    def __init__(self):
        self.data = "not a completion"


def test_openai_on_input_handler_with_completion_instance():
    """Test that openai_on_input_handler processes completion instances correctly"""
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
    """Test that openai_on_input_handler handles non-completion instances correctly"""
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
    """Test that openai_on_input_handler handles EasyPrompt correctly"""
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
    """Test that openai_on_input_handler preserves original args and kwargs"""
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
    """Test openai_on_input_handler behavior with no arguments"""
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
