import pytest

from weave.integrations.openai.openai_sdk import (
    create_wrapper_async,
    create_wrapper_sync,
)
from weave.trace.autopatch import OpSettings


class DummyClient:
    def __init__(self, base_url: str):
        self._base_url = base_url


class DummyCompletion:
    def __init__(self, base_url: str):
        self._client = DummyClient(base_url)


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
