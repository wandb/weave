import os
from collections.abc import Generator
from pathlib import Path

import pytest
from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.llms import ChatMessage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.tools import FunctionTool
from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.openai import OpenAI
from pydantic import BaseModel

from weave.integrations.integration_utilities import (
    filter_body,
    flatten_calls,
    flattened_calls_to_names,
    op_name_from_ref,
)
from weave.integrations.llamaindex.llamaindex import llamaindex_patcher
from weave.integrations.openai.openai_sdk import get_openai_patcher
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import CallsFilter


@pytest.fixture(autouse=True)
def patch_llamaindex() -> Generator[None, None, None]:
    """Patch LlamaIndex for all tests in this file."""
    # Patch both LlamaIndex and OpenAI since LlamaIndex uses OpenAI as backend
    llamaindex_patcher.attempt_patch()
    openai_patcher = get_openai_patcher()
    openai_patcher.attempt_patch()

    yield

    llamaindex_patcher.undo_patch()
    openai_patcher.undo_patch()


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_llamaindex_llm_complete_sync(client: WeaveClient) -> None:
    """Test synchronous LLM complete operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    response = llm.complete("William Shakespeare is ")

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.complete", 0),
        ("llama_index.event.LLMCompletion", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert call_0.started_at < call_0.ended_at
    assert call_0.parent_id is None
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert len(call_0.output["text"]) > 0
    assert call_0.output["text"] == response.text
    assert list(call_0.output["additional_kwargs"].keys()) == [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ]

    call_1, _ = flattened_calls[1]
    assert call_1.started_at < call_1.ended_at
    assert call_1.parent_id == call_0.id
    assert call_1.inputs["class_name"] == "LLMCompletionStartEvent"
    assert call_1.inputs["prompt"] == "William Shakespeare is "
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert call_1.output["class_name"] == "LLMCompletionEndEvent"
    assert len(call_1.output["response"]["text"]) > 0
    assert call_1.output["response"]["additional_kwargs"]["prompt_tokens"] == 11
    assert call_1.output["response"]["additional_kwargs"]["completion_tokens"] == 195

    call_2, _ = flattened_calls[2]
    assert call_2.started_at < call_2.ended_at
    assert call_2.parent_id == call_1.id
    assert call_2.inputs["model"] == "gpt-4o-mini"
    assert call_2.inputs["temperature"] == 0.1
    assert call_2.inputs["messages"] == [
        {"role": "user", "content": "William Shakespeare is "}
    ]
    assert call_2.inputs["stream"] == False
    assert "id" in call_2.output
    assert "choices" in call_2.output
    assert len(call_2.output["choices"]) == 1
    assert call_2.output["choices"][0]["finish_reason"] == "stop"
    assert call_2.output["choices"][0]["index"] == 0
    assert "message" in call_2.output["choices"][0]
    assert call_2.output["choices"][0]["message"]["role"] == "assistant"
    assert len(call_2.output["choices"][0]["message"]["content"]) > 0
    assert call_2.output["usage"]["prompt_tokens"] == 11
    assert call_2.output["usage"]["completion_tokens"] == 195
    assert call_2.output["usage"]["total_tokens"] == 206


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_llm_complete_async(client: WeaveClient) -> None:
    """Test asynchronous LLM complete operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    response = await llm.acomplete("William Shakespeare is ")

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.acomplete", 0),
        ("llama_index.event.LLMCompletion", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert call_0.started_at < call_0.ended_at
    assert call_0.parent_id is None
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["self"] == "William Shakespeare is "
    assert len(call_0.output["text"]) > 0
    assert call_0.output["additional_kwargs"]["prompt_tokens"] == 11
    assert call_0.output["additional_kwargs"]["completion_tokens"] == 211

    call_1, _ = flattened_calls[1]
    assert call_1.started_at < call_1.ended_at
    assert call_1.parent_id == call_0.id
    assert call_1.inputs["prompt"] == "William Shakespeare is "
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert len(call_1.output["response"]["text"]) > 0
    assert call_1.output["response"]["additional_kwargs"]["prompt_tokens"] == 11
    assert call_1.output["response"]["additional_kwargs"]["completion_tokens"] == 211

    call_2, _ = flattened_calls[2]
    assert call_2.started_at < call_2.ended_at
    assert call_2.parent_id == call_1.id
    assert call_2.inputs["model"] == "gpt-4o-mini"
    assert call_2.inputs["temperature"] == 0.1
    assert call_2.inputs["messages"] == [
        {"role": "user", "content": "William Shakespeare is "}
    ]
    assert call_2.inputs["stream"] == False
    assert "id" in call_2.output
    assert "choices" in call_2.output
    assert len(call_2.output["choices"]) == 1
    assert call_2.output["choices"][0]["finish_reason"] == "stop"
    assert call_2.output["choices"][0]["index"] == 0
    assert "message" in call_2.output["choices"][0]
    assert call_2.output["choices"][0]["message"]["role"] == "assistant"
    assert len(call_2.output["choices"][0]["message"]["content"]) > 0
    assert call_2.output["usage"]["prompt_tokens"] == 11
    assert call_2.output["usage"]["completion_tokens"] == 211
    assert call_2.output["usage"]["total_tokens"] == 222


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_llamaindex_llm_stream_complete_sync(client: WeaveClient) -> None:
    """Test synchronous LLM streaming complete operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    handle = llm.stream_complete("William Shakespeare is ")

    all_content = ""
    for token in handle:
        if token.delta:
            all_content += token.delta

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.stream_complete", 0),
        ("llama_index.event.LLMCompletion", 1),
        ("llama_index.event.LLMCompletionInProgress", 2),
        ("openai.chat.completions.create", 3),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert call_0.started_at < call_0.ended_at
    assert call_0.parent_id is None
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["self"] == "William Shakespeare is "
    assert "result" in call_0.output
    assert call_0.output["result"].startswith("<generator object")

    call_1, _ = flattened_calls[1]
    assert call_1.started_at < call_1.ended_at
    assert call_1.parent_id == call_0.id
    assert call_1.inputs["prompt"] == "William Shakespeare is "
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert "response" in call_1.output
    assert "text" in call_1.output["response"]
    assert len(call_1.output["response"]["text"]) > 0

    call_2, _ = flattened_calls[2]
    assert call_2.started_at < call_2.ended_at
    assert call_2.parent_id == call_1.id
    assert call_2.inputs["prompt"] == "William Shakespeare is "
    assert call_2.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_2.inputs["model_dict"]["temperature"] == 0.1
    assert "response" in call_2.output
    assert "text" in call_2.output["response"]
    assert len(call_2.output["response"]["text"]) > 0

    call_3, _ = flattened_calls[3]
    assert call_3.started_at < call_3.ended_at
    assert call_3.parent_id == call_2.id
    assert call_3.inputs["model"] == "gpt-4o-mini"
    assert call_3.inputs["temperature"] == 0.1
    assert call_3.inputs["stream"] == True
    assert call_3.inputs["messages"] == [
        {"role": "user", "content": "William Shakespeare is "}
    ]
    assert "id" in call_3.output
    assert "choices" in call_3.output
    assert len(call_3.output["choices"]) == 1
    assert call_3.output["choices"][0]["finish_reason"] == "stop"
    assert call_3.output["choices"][0]["index"] == 0
    assert "message" in call_3.output["choices"][0]
    assert call_3.output["choices"][0]["message"]["role"] == "assistant"
    assert len(call_3.output["choices"][0]["message"]["content"]) > 0
    assert call_3.output["usage"]["prompt_tokens"] == 11
    assert call_3.output["usage"]["completion_tokens"] == 160
    assert call_3.output["usage"]["total_tokens"] == 171


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_llm_stream_complete_async(client: WeaveClient) -> None:
    """Test asynchronous LLM streaming complete operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    handle = await llm.astream_complete("William Shakespeare is ")

    all_content = ""
    async for token in handle:
        if token.delta:
            all_content += token.delta

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.astream_complete", 0),
        ("llama_index.event.LLMCompletion", 1),
        ("llama_index.event.LLMCompletionInProgress", 2),
        ("openai.chat.completions.create", 3),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert call_0.inputs["self"] == "William Shakespeare is "
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["api_key"] == "REDACTED"
    assert call_0.inputs["api_base"] == "https://api.openai.com/v1"
    assert "result" in call_0.output

    call_1, _ = flattened_calls[1]
    assert call_1.inputs["prompt"] == "William Shakespeare is "
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert call_1.inputs["class_name"] == "LLMCompletionStartEvent"
    assert "response" in call_1.output
    assert call_1.output["response"]["text"] == all_content

    call_2, _ = flattened_calls[2]
    assert call_2.inputs["prompt"] == "William Shakespeare is "
    assert call_2.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_2.inputs["model_dict"]["temperature"] == 0.1
    assert call_2.inputs["class_name"] == "LLMCompletionStartEvent"
    assert "response" in call_2.output
    assert call_2.output["response"]["text"] == all_content

    call_3, _ = flattened_calls[3]
    assert call_3.inputs["messages"] == [
        {"role": "user", "content": "William Shakespeare is "}
    ]
    assert call_3.inputs["model"] == "gpt-4o-mini"
    assert call_3.inputs["stream"] == True
    assert call_3.inputs["temperature"] == 0.1
    assert "id" in call_3.output
    assert "choices" in call_3.output
    assert len(call_3.output["choices"]) == 1
    assert call_3.output["choices"][0]["finish_reason"] == "stop"
    assert call_3.output["choices"][0]["index"] == 0
    assert "message" in call_3.output["choices"][0]
    assert call_3.output["choices"][0]["message"]["role"] == "assistant"
    assert call_3.output["choices"][0]["message"]["content"] == all_content
    assert call_3.output["usage"]["prompt_tokens"] == 11
    assert call_3.output["usage"]["completion_tokens"] == 192
    assert call_3.output["usage"]["total_tokens"] == 203


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_llamaindex_llm_chat_sync(client: WeaveClient) -> None:
    """Test synchronous LLM chat operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Tell me a joke."),
    ]

    response = llm.chat(messages)

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.chat", 0),
        ("llama_index.event.LLMChat", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["_self"]["ChatMessage_0"]["role"] == "system"
    assert (
        call_0.inputs["_self"]["ChatMessage_0"]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_0.inputs["_self"]["ChatMessage_1"]["role"] == "user"
    assert (
        call_0.inputs["_self"]["ChatMessage_1"]["blocks"][0]["text"]
        == "Tell me a joke."
    )
    assert call_0.output["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_0.output["message"]["blocks"][0]["text"]
    )
    assert call_0.output["raw"]["usage"]["prompt_tokens"] == 22
    assert call_0.output["raw"]["usage"]["completion_tokens"] == 17
    assert call_0.output["raw"]["usage"]["total_tokens"] == 39

    call_1, _ = flattened_calls[1]
    assert call_1.inputs["messages"][0]["role"] == "system"
    assert (
        call_1.inputs["messages"][0]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_1.inputs["messages"][1]["role"] == "user"
    assert call_1.inputs["messages"][1]["blocks"][0]["text"] == "Tell me a joke."
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert call_1.output["response"]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_1.output["response"]["message"]["blocks"][0]["text"]
    )

    call_2, _ = flattened_calls[2]
    assert call_2.inputs["messages"] == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."},
    ]
    assert call_2.inputs["model"] == "gpt-4o-mini"
    assert call_2.inputs["temperature"] == 0.1
    assert call_2.inputs["stream"] == False
    assert call_2.output["choices"][0]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_2.output["choices"][0]["message"]["content"]
    )
    assert call_2.output["usage"]["prompt_tokens"] == 22
    assert call_2.output["usage"]["completion_tokens"] == 17
    assert call_2.output["usage"]["total_tokens"] == 39


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_llm_chat_async(client: WeaveClient) -> None:
    """Test asynchronous LLM chat operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Tell me a joke."),
    ]

    response = await llm.achat(messages)

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.achat", 0),
        ("llama_index.event.LLMChat", 1),
        ("openai.chat.completions.create", 2),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert call_0.started_at < call_0.ended_at
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["_self"]["ChatMessage_0"]["role"] == "system"
    assert (
        call_0.inputs["_self"]["ChatMessage_0"]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_0.inputs["_self"]["ChatMessage_1"]["role"] == "user"
    assert (
        call_0.inputs["_self"]["ChatMessage_1"]["blocks"][0]["text"]
        == "Tell me a joke."
    )
    assert call_0.output["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_0.output["message"]["blocks"][0]["text"]
    )

    call_1, _ = flattened_calls[1]
    assert call_1.started_at < call_1.ended_at
    assert call_1.inputs["messages"][0]["role"] == "system"
    assert (
        call_1.inputs["messages"][0]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_1.inputs["messages"][1]["role"] == "user"
    assert call_1.inputs["messages"][1]["blocks"][0]["text"] == "Tell me a joke."
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert call_1.output["response"]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_1.output["response"]["message"]["blocks"][0]["text"]
    )

    call_2, _ = flattened_calls[2]
    assert call_2.started_at < call_2.ended_at
    assert call_2.inputs["messages"] == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."},
    ]
    assert call_2.inputs["model"] == "gpt-4o-mini"
    assert call_2.inputs["temperature"] == 0.1
    assert call_2.inputs["stream"] == False
    assert call_2.output["choices"][0]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_2.output["choices"][0]["message"]["content"]
    )
    assert call_2.output["usage"]["prompt_tokens"] == 22
    assert call_2.output["usage"]["completion_tokens"] == 17
    assert call_2.output["usage"]["total_tokens"] == 39


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_llamaindex_llm_stream_chat_sync(client: WeaveClient) -> None:
    """Test synchronous LLM streaming chat operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Tell me a joke."),
    ]

    handle = llm.stream_chat(messages)

    all_content = ""
    for token in handle:
        if token.delta:
            all_content += token.delta

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.stream_chat", 0),
        ("llama_index.event.LLMChat", 1),
        ("llama_index.event.LLMChatInProgress", 2),
        ("openai.chat.completions.create", 3),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    # Check call_0: OpenAI.stream_chat span
    assert op_name_from_ref(call_0.op_name) == "llama_index.span.OpenAI.stream_chat"
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["api_key"] == "REDACTED"
    assert call_0.inputs["_self"]["ChatMessage_0"]["role"] == "system"
    assert (
        call_0.inputs["_self"]["ChatMessage_0"]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_0.inputs["_self"]["ChatMessage_1"]["role"] == "user"
    assert (
        call_0.inputs["_self"]["ChatMessage_1"]["blocks"][0]["text"]
        == "Tell me a joke."
    )
    assert call_0.summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 22
    assert call_0.summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 17
    assert call_0.summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 39

    # Check call_1: LLMChat event
    call_1, _ = flattened_calls[1]
    assert op_name_from_ref(call_1.op_name) == "llama_index.event.LLMChat"
    assert call_1.inputs["messages"][0]["role"] == "system"
    assert (
        call_1.inputs["messages"][0]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_1.inputs["messages"][1]["role"] == "user"
    assert call_1.inputs["messages"][1]["blocks"][0]["text"] == "Tell me a joke."
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.inputs["model_dict"]["temperature"] == 0.1
    assert call_1.output["response"]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_1.output["response"]["message"]["blocks"][0]["text"]
    )
    assert call_1.summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 22
    assert call_1.summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 17
    assert call_1.summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 39

    # Check call_2: LLMChatInProgress event
    call_2, _ = flattened_calls[2]
    assert op_name_from_ref(call_2.op_name) == "llama_index.event.LLMChatInProgress"
    assert call_2.inputs["messages"][0]["role"] == "system"
    assert call_2.inputs["messages"][1]["role"] == "user"
    assert call_2.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_2.output["response"]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_2.output["response"]["message"]["blocks"][0]["text"]
    )
    assert call_2.summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 22
    assert call_2.summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 17
    assert call_2.summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 39

    # Check call_3: openai.chat.completions.create
    call_3, _ = flattened_calls[3]
    assert op_name_from_ref(call_3.op_name) == "openai.chat.completions.create"
    assert call_3.inputs["model"] == "gpt-4o-mini"
    assert call_3.inputs["stream"] is True
    assert call_3.inputs["temperature"] == 0.1
    assert call_3.inputs["messages"][0]["role"] == "system"
    assert call_3.inputs["messages"][0]["content"] == "You are a helpful assistant."
    assert call_3.inputs["messages"][1]["role"] == "user"
    assert call_3.inputs["messages"][1]["content"] == "Tell me a joke."
    assert call_3.output["choices"][0]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_3.output["choices"][0]["message"]["content"]
    )
    assert call_3.output["usage"]["prompt_tokens"] == 22
    assert call_3.output["usage"]["completion_tokens"] == 17
    assert call_3.output["usage"]["total_tokens"] == 39


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_llm_stream_chat_async(client: WeaveClient) -> None:
    """Test asynchronous LLM streaming chat operation."""
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Tell me a joke."),
    ]

    handle = await llm.astream_chat(messages)

    all_content = ""
    async for token in handle:
        if token.delta:
            all_content += token.delta

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    exp = [
        ("llama_index.span.OpenAI.astream_chat", 0),
        ("llama_index.event.LLMChat", 1),
        ("llama_index.event.LLMChatInProgress", 2),
        ("openai.chat.completions.create", 3),
    ]
    assert flattened_calls_to_names(flattened_calls) == exp

    call_0, _ = flattened_calls[0]
    assert op_name_from_ref(call_0.op_name) == "llama_index.span.OpenAI.astream_chat"
    assert call_0.inputs["model"] == "gpt-4o-mini"
    assert call_0.inputs["temperature"] == 0.1
    assert call_0.inputs["api_key"] == "REDACTED"
    assert call_0.inputs["_self"]["ChatMessage_0"]["role"] == "system"
    assert (
        call_0.inputs["_self"]["ChatMessage_0"]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_0.inputs["_self"]["ChatMessage_1"]["role"] == "user"
    assert (
        call_0.inputs["_self"]["ChatMessage_1"]["blocks"][0]["text"]
        == "Tell me a joke."
    )
    assert "<async_generator object" in call_0.output["result"]
    assert call_0.summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 22
    assert call_0.summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 17
    assert call_0.summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 39

    call_1, _ = flattened_calls[1]
    assert op_name_from_ref(call_1.op_name) == "llama_index.event.LLMChat"
    assert call_1.inputs["messages"][0]["role"] == "system"
    assert (
        call_1.inputs["messages"][0]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_1.inputs["messages"][1]["role"] == "user"
    assert call_1.inputs["messages"][1]["blocks"][0]["text"] == "Tell me a joke."
    assert call_1.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_1.output["response"]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_1.output["response"]["message"]["blocks"][0]["text"]
    )
    assert call_1.summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 22
    assert call_1.summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 17
    assert call_1.summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 39

    call_2, _ = flattened_calls[2]
    assert op_name_from_ref(call_2.op_name) == "llama_index.event.LLMChatInProgress"
    assert call_2.inputs["messages"][0]["role"] == "system"
    assert (
        call_2.inputs["messages"][0]["blocks"][0]["text"]
        == "You are a helpful assistant."
    )
    assert call_2.inputs["messages"][1]["role"] == "user"
    assert call_2.inputs["messages"][1]["blocks"][0]["text"] == "Tell me a joke."
    assert call_2.inputs["model_dict"]["model"] == "gpt-4o-mini"
    assert call_2.output["response"]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_2.output["response"]["message"]["blocks"][0]["text"]
    )
    assert call_2.summary["usage"]["gpt-4o-mini-2024-07-18"]["prompt_tokens"] == 22
    assert call_2.summary["usage"]["gpt-4o-mini-2024-07-18"]["completion_tokens"] == 17
    assert call_2.summary["usage"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 39

    call_3, _ = flattened_calls[3]
    assert op_name_from_ref(call_3.op_name) == "openai.chat.completions.create"
    assert call_3.inputs["model"] == "gpt-4o-mini"
    assert call_3.inputs["stream"] is True
    assert call_3.inputs["temperature"] == 0.1
    assert call_3.inputs["messages"][0]["role"] == "system"
    assert call_3.inputs["messages"][0]["content"] == "You are a helpful assistant."
    assert call_3.inputs["messages"][1]["role"] == "user"
    assert call_3.inputs["messages"][1]["content"] == "Tell me a joke."
    assert call_3.output["choices"][0]["message"]["role"] == "assistant"
    assert (
        "Why did the scarecrow win an award?"
        in call_3.output["choices"][0]["message"]["content"]
    )
    assert call_3.output["usage"]["prompt_tokens"] == 22
    assert call_3.output["usage"]["completion_tokens"] == 17
    assert call_3.output["usage"]["total_tokens"] == 39


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
def test_llamaindex_tool_calling_sync(client: WeaveClient) -> None:
    """Test synchronous LLM tool calling operation."""

    class Song(BaseModel):
        name: str
        artist: str

    def generate_song(name: str, artist: str) -> Song:
        """Generates a song with provided name and artist."""
        return Song(name=name, artist=artist)

    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")
    llm = OpenAI(model="gpt-4o-mini", api_key=api_key)
    tool = FunctionTool.from_defaults(fn=generate_song)

    response = llm.predict_and_call([tool], "Pick a random song for me")

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    # Verify we have the expected call structure
    assert len(flattened_calls) == 7

    # Find the main predict_and_call operation
    main_call = None
    for call, _ in flattened_calls:
        if "predict_and_call" in op_name_from_ref(call.op_name):
            main_call = call
            break

    assert main_call is not None, "Could not find predict_and_call operation"
    assert main_call.started_at < main_call.ended_at
    assert main_call.parent_id is None
    assert main_call.inputs["model"] == "gpt-4o-mini"
    assert main_call.inputs["temperature"] == 0.1

    # Verify the tool was provided in inputs
    assert "tools" in main_call.inputs or "_self" in main_call.inputs

    # Verify output contains song information
    assert main_call.output is not None

    # Check that we have OpenAI completion calls
    openai_calls = [
        call
        for call, _ in flattened_calls
        if "openai.chat.completions.create" in op_name_from_ref(call.op_name)
    ]
    assert len(openai_calls) >= 1, "Should have at least one OpenAI completion call"

    # Verify the OpenAI call has the correct structure
    openai_call = openai_calls[0]
    assert openai_call.inputs["model"] == "gpt-4o-mini"
    assert openai_call.inputs["temperature"] == 0.1
    assert "tools" in openai_call.inputs  # Tool calling should include tools parameter
    assert openai_call.inputs["stream"] == False

    # Verify the tool was defined correctly in the OpenAI call
    tools = openai_call.inputs["tools"]
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "generate_song"
    assert "name" in tools[0]["function"]["parameters"]["properties"]
    assert "artist" in tools[0]["function"]["parameters"]["properties"]


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_workflow(client: WeaveClient) -> None:
    """Test LlamaIndex workflow execution."""

    class FirstEvent(Event):
        first_output: str

    class SecondEvent(Event):
        second_output: str

    class TestWorkflow(Workflow):
        @step
        async def step_one(self, ev: StartEvent) -> FirstEvent:
            return FirstEvent(first_output="First step complete.")

        @step
        async def step_two(self, ev: FirstEvent) -> SecondEvent:
            return SecondEvent(second_output="Second step complete.")

        @step
        async def step_three(self, ev: SecondEvent) -> StopEvent:
            return StopEvent(result="Workflow complete.")

    # Execute the workflow
    workflow = TestWorkflow(timeout=10, verbose=False)
    result = await workflow.run(first_input="Start the workflow.")

    # Verify the workflow result
    assert result == "Workflow complete."

    # Check the captured calls
    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)
    print(flattened_calls_to_names(flattened_calls))

    # LlamaIndex 0.14.1+ no longer emits TestWorkflow-done span and SpanDrop event
    # Expected hierarchy: run -> step_one, step_two, step_three
    assert len(flattened_calls) == 4


@pytest.mark.skip_clickhouse_client
@pytest.mark.vcr(
    filter_headers=["authorization"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
    # before_record_request=filter_body,
)
@pytest.mark.asyncio
async def test_llamaindex_quick_start(client: WeaveClient) -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "sk-DUMMY_KEY")

    # Get paths relative to this test file
    test_dir = Path(__file__).parent
    test_data_dir = test_dir / "test_data"
    vector_index_dir = test_dir / "vector_index"

    documents = SimpleDirectoryReader(str(test_data_dir)).load_data()
    parser = SentenceSplitter()
    nodes = parser.get_nodes_from_documents(documents)

    if os.path.exists(vector_index_dir):
        storage_context = StorageContext.from_defaults(
            persist_dir=str(vector_index_dir)
        )
        index = load_index_from_storage(storage_context)
    else:
        os.makedirs(vector_index_dir, exist_ok=True)
        index = VectorStoreIndex(nodes)
        index.storage_context.persist(str(vector_index_dir))

    query_engine = index.as_query_engine()

    def multiply(a: float, b: float) -> float:
        """Useful for multiplying two numbers."""
        return a * b

    async def search_documents(query: str) -> str:
        """Useful for answering natural language questions about an personal essay written by Paul Graham."""
        response = await query_engine.aquery(query)
        return str(response)

    # Create an enhanced workflow with both tools
    agent = FunctionAgent(
        tools=[multiply, search_documents],
        llm=OpenAI(model="gpt-4o-mini", api_key=api_key),
        system_prompt="""You are a helpful assistant that can perform calculations
        and search through documents to answer questions.""",
    )

    # Now we can ask questions about the documents or do calculations
    response = await agent.run("What did the author do in college? Also, what's 7 * 8?")

    calls = list(client.get_calls(filter=CallsFilter(trace_roots_only=True)))
    flattened_calls = flatten_calls(calls)

    # LlamaIndex 0.14.1+ no longer emits FunctionAgent-done span and SpanDrop event
    names = flattened_calls_to_names(flattened_calls)
    # Streaming chat can emit multiple LLMChatInProgress events depending on chunking.
    # Collapse consecutive duplicates to avoid flakes across platforms.
    normalized_names: list[tuple[str, int]] = []
    for name, depth in names:
        if (
            normalized_names
            and normalized_names[-1] == (name, depth)
            and name == "llama_index.event.LLMChatInProgress"
        ):
            continue
        normalized_names.append((name, depth))

    assert len(normalized_names) == 48
    assert normalized_names == [
        ("llama_index.span.SentenceSplitter-parse_nodes", 0),
        ("llama_index.span.SentenceSplitter.split_text_metadata_aware", 1),
        ("llama_index.span.FunctionAgent.run", 0),
        ("llama_index.span.FunctionAgent.init_run", 1),
        ("llama_index.span.FunctionAgent.setup_agent", 1),
        ("llama_index.span.FunctionAgent.run_agent_step", 1),
        ("llama_index.span.OpenAI-prepare_chat_with_tools", 2),
        ("llama_index.span.OpenAI.astream_chat", 2),
        ("llama_index.event.LLMChat", 3),
        ("llama_index.event.LLMChatInProgress", 4),
        ("openai.chat.completions.create", 5),
        ("llama_index.span.FunctionAgent.parse_agent_output", 1),
        ("llama_index.span.FunctionAgent.call_tool", 1),
        ("llama_index.span.FunctionTool.acall", 2),
        ("llama_index.span.RetrieverQueryEngine.aquery", 3),
        ("llama_index.event.Query", 4),
        ("llama_index.span.RetrieverQueryEngine-aquery", 4),
        ("llama_index.span.VectorIndexRetriever.aretrieve", 5),
        ("llama_index.event.Retrieval", 6),
        ("llama_index.span.VectorIndexRetriever-aretrieve", 6),
        ("llama_index.span.OpenAIEmbedding.aget_query_embedding", 7),
        ("llama_index.event.Embedding", 8),
        ("llama_index.span.OpenAIEmbedding-aget_query_embedding", 8),
        ("openai.embeddings.create", 9),
        ("llama_index.span.CompactAndRefine.asynthesize", 5),
        ("llama_index.event.Synthesize", 6),
        ("llama_index.span.CompactAndRefine.aget_response", 6),
        ("llama_index.span.TokenTextSplitter.split_text", 7),
        ("llama_index.span.CompactAndRefine.aget_response", 7),
        ("llama_index.event.GetResponse", 8),
        ("llama_index.span.TokenTextSplitter.split_text", 8),
        ("llama_index.span.OpenAI.apredict", 8),
        ("llama_index.event.LLMPredict", 9),
        ("llama_index.span.OpenAI.achat", 9),
        ("llama_index.event.LLMChat", 10),
        ("openai.chat.completions.create", 11),
        ("llama_index.span.FunctionAgent.call_tool", 1),
        ("llama_index.span.FunctionTool.acall", 2),
        ("llama_index.span.FunctionAgent.aggregate_tool_results", 1),
        ("llama_index.span.FunctionAgent.aggregate_tool_results", 1),
        ("llama_index.span.FunctionAgent.setup_agent", 1),
        ("llama_index.span.FunctionAgent.run_agent_step", 1),
        ("llama_index.span.OpenAI-prepare_chat_with_tools", 2),
        ("llama_index.span.OpenAI.astream_chat", 2),
        ("llama_index.event.LLMChat", 3),
        ("llama_index.event.LLMChatInProgress", 4),
        ("openai.chat.completions.create", 5),
        ("llama_index.span.FunctionAgent.parse_agent_output", 1),
    ]
