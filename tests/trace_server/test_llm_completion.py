import datetime
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from weave.trace_server import clickhouse_trace_server_batched as chts
from weave.trace_server import llm_completion as llm_mod
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
    MissingLLMApiKeyError,
    NotFoundError,
)
from weave.trace_server.interface.builtin_object_classes.provider import Provider
from weave.trace_server.llm_completion import (
    get_custom_provider_info,
    resolve_and_apply_prompt,
    resolve_prompt_messages,
)
from weave.trace_server.secret_fetcher_context import _secret_fetcher_context

LITELLM_STREAM = (
    "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion_stream"
)
LITELLM_COMPLETION = (
    "weave.trace_server.clickhouse_trace_server_batched.lite_llm_completion"
)
AGENT_WRITER = "weave.trace_server.clickhouse_trace_server_batched.AgentWriteHandler"


class StreamingException(Exception):
    """Sentinel exception raised by a mocked litellm stream."""


@pytest.fixture(autouse=True)
def _clear_custom_provider_cache():
    """Reset the module-level custom-provider TTL cache between tests."""
    with llm_mod._custom_provider_cache_lock:
        llm_mod._custom_provider_cache.clear()


# --- get_custom_provider_info --------------------------------------------------


def test_successful_provider_info_fetch():
    """Provider + model objects and API key are resolved into a populated ProviderInfo."""
    project_id = "test-project"
    provider_id = "test-provider"
    model_name = f"{provider_id}/test-model"
    provider_obj = _provider_obj(project_id, provider_id)
    model_obj = _provider_model_obj(
        project_id, f"{provider_id}-test-model", provider_id
    )

    obj_read = MagicMock(
        side_effect=_obj_read_router({provider_id: provider_obj, model_name: model_obj})
    )
    secret_fetcher = _secret_fetcher({"TEST_API_KEY": "test-api-key-value"})
    token = _secret_fetcher_context.set(secret_fetcher)
    try:
        info = get_custom_provider_info(
            project_id=project_id,
            provider_name=provider_id,
            model_name=model_name,
            obj_read_func=obj_read,
        )
        assert info.base_url == "https://api.example.com"
        assert info.api_key == "test-api-key-value"
        assert info.extra_headers == {"X-Header": "value"}
        assert info.return_type == "openai"
        assert info.actual_model_name == "actual-model-name"
        obj_read.assert_called()
        secret_fetcher.fetch.assert_called_with("TEST_API_KEY")
    finally:
        _secret_fetcher_context.reset(token)


@pytest.mark.parametrize(
    ("scenario", "expected_message"),
    [
        ("missing_secret_fetcher", "No secret fetcher found"),
        ("provider_not_found", "Failed to fetch provider model information"),
        ("wrong_provider_type", "Could not find Provider"),
        ("wrong_provider_model_type", "Could not find Provider"),
    ],
)
def test_get_custom_provider_info_error_paths(scenario, expected_message):
    """Missing fetcher, unreadable objects, and wrong object types each raise InvalidRequest."""
    project_id = "test-project"
    provider_id = "test-provider"
    model_name = f"{provider_id}/test-model"
    provider_obj = _provider_obj(project_id, provider_id)
    model_obj = _provider_model_obj(
        project_id, f"{provider_id}-test-model", provider_id
    )
    secret_fetcher = _secret_fetcher({"TEST_API_KEY": "test-api-key-value"})

    if scenario == "missing_secret_fetcher":
        obj_read: Callable[[tsi.ObjReadReq], tsi.ObjReadRes] = MagicMock()
        fetcher = None
    elif scenario == "provider_not_found":
        obj_read = MagicMock(side_effect=NotFoundError("Provider not found"))
        fetcher = secret_fetcher
    elif scenario == "wrong_provider_type":
        wrong = provider_obj.model_copy()
        wrong.base_object_class = "NotAProvider"
        obj_read = MagicMock(
            side_effect=_obj_read_router({provider_id: wrong}, default=model_obj)
        )
        fetcher = secret_fetcher
    elif scenario == "wrong_provider_model_type":
        wrong = model_obj.model_copy()
        wrong.base_object_class = "NotAProviderModel"
        obj_read = MagicMock(
            side_effect=_obj_read_router({provider_id: provider_obj}, default=wrong)
        )
        fetcher = secret_fetcher
    else:
        raise AssertionError(f"unhandled scenario: {scenario}")

    token = _secret_fetcher_context.set(fetcher)
    try:
        with pytest.raises(InvalidRequest, match=expected_message):
            get_custom_provider_info(
                project_id=project_id,
                provider_name=provider_id,
                model_name=model_name,
                obj_read_func=obj_read,
            )
    finally:
        _secret_fetcher_context.reset(token)


# --- streaming completions -----------------------------------------------------


def test_basic_streaming_completion(streaming_server):
    """Content deltas and the terminal usage chunk pass through verbatim."""
    chunks_in = [
        _delta_chunk("Hello"),
        _delta_chunk(" world"),
        _stop_chunk({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}),
    ]
    with patch(LITELLM_STREAM, return_value=_iter_mock(chunks_in)):
        chunks = list(
            streaming_server.completions_create_stream(
                _completion_req("test_project", track=False)
            )
        )
    assert len(chunks) == 3
    assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
    assert chunks[1]["choices"][0]["delta"]["content"] == " world"
    assert chunks[2]["choices"][0]["finish_reason"] == "stop"
    assert "usage" in chunks[2]


@pytest.mark.parametrize(
    "exc",
    [
        StreamingException("Test error"),
        MissingLLMApiKeyError("No API key found", api_key_name="TEST_API_KEY"),
    ],
    ids=["generic_error", "missing_api_key"],
)
def test_streaming_propagates_litellm_errors(streaming_server, exc):
    """Errors raised by the litellm stream propagate out of the generator."""
    with patch(LITELLM_STREAM, side_effect=exc):
        with pytest.raises(type(exc)):
            list(
                streaming_server.completions_create_stream(
                    _completion_req("test_project", track=False)
                )
            )


def test_streaming_with_call_tracking(streaming_server):
    """Tracking emits a leading _meta chunk and writes open + completed spans."""
    chunks_in = [
        _delta_chunk("Hello"),
        _stop_chunk({"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}),
    ]
    with (
        patch(LITELLM_STREAM, return_value=_iter_mock(chunks_in)),
        patch(AGENT_WRITER) as writer_cls,
    ):
        writer = writer_cls.return_value
        chunks = list(
            streaming_server.completions_create_stream(
                _completion_req("dGVzdF9wcm9qZWN0", track=True)
            )
        )
    assert len(chunks) == 3
    assert "_meta" in chunks[0]
    assert "weave_call_id" in chunks[0]["_meta"]
    assert chunks[1]["choices"][0]["delta"]["content"] == "Hello"
    assert chunks[2]["choices"][0]["finish_reason"] == "stop"
    assert writer.insert_span.call_count == 2
    completed_span = writer.insert_span.call_args_list[1][0][0]
    assert completed_span.project_id == "dGVzdF9wcm9qZWN0"


def test_custom_provider_streaming(streaming_server):
    """A custom:: model resolves provider config and forwards base_url + extra_headers."""
    chunks_in = [
        _delta_chunk("Custom", model="custom-model"),
        _stop_chunk(
            {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            model="custom-model",
        ),
    ]
    provider = _provider_obj(
        "test_project",
        "custom-provider",
        base_url="https://api.custom.com",
        api_key_name="CUSTOM_API_KEY",
        extra_headers={"X-Custom": "value"},
        extra_val={"api_base": "https://api.custom.com"},
    )
    model = _provider_model_obj(
        "test_project", "custom-provider-model", "custom-provider", name="custom-model"
    )
    with (
        patch(LITELLM_STREAM, return_value=_iter_mock(chunks_in)) as mock_litellm,
        patch.object(
            chts.ClickHouseTraceServer,
            "obj_read",
            side_effect=_obj_read_router(
                {"custom-provider": provider, "custom-provider-model": model}
            ),
        ),
    ):
        req = _completion_req(
            "dGVzdF9wcm9qZWN0", track=False, model="custom::custom-provider::model"
        )
        chunks = list(streaming_server.completions_create_stream(req))
    assert len(chunks) == 2
    assert chunks[0]["choices"][0]["delta"]["content"] == "Custom"
    assert chunks[1]["choices"][0]["finish_reason"] == "stop"
    mock_litellm.assert_called_once()
    call_args = mock_litellm.call_args[1]
    assert (
        call_args.get("api_base") or call_args.get("base_url")
    ) == "https://api.custom.com"
    assert call_args["extra_headers"] == {"X-Custom": "value"}


# --- prompt resolution ---------------------------------------------------------


def test_resolve_prompt_messages():
    """resolve_prompt_messages returns prompt messages without substituting template vars."""
    project_id = "test-project"
    prompt_obj = _messages_prompt_obj(
        project_id,
        [
            {"role": "system", "content": "You are {assistant_name}."},
            {"role": "user", "content": "Hello!"},
        ],
    )
    messages = resolve_prompt_messages(
        prompt=_prompt_uri(project_id, "test-prompt"),
        project_id=project_id,
        obj_read_func=lambda req: tsi.ObjReadRes(obj=prompt_obj),
    )
    assert messages == [
        {"role": "system", "content": "You are {assistant_name}."},
        {"role": "user", "content": "Hello!"},
    ]


def test_resolve_prompt_messages_invalid_prompt():
    """A non-Prompt object raises InvalidRequest."""
    project_id = "test-project"
    not_prompt = _model_obj(project_id, "test-obj")
    with pytest.raises(InvalidRequest, match="is not a Prompt or MessagesPrompt"):
        resolve_prompt_messages(
            prompt=_prompt_uri(project_id, "test-obj"),
            project_id=project_id,
            obj_read_func=lambda req: tsi.ObjReadRes(obj=not_prompt),
        )


def test_streaming_with_prompt_resolution(streaming_server):
    """A prompt reference is resolved via obj_read before streaming."""
    project_id = "test-project"
    prompt_obj = _messages_prompt_obj(
        project_id, [{"role": "system", "content": "You are a helpful assistant."}]
    )
    chunks_in = [
        _delta_chunk("Hello"),
        _stop_chunk({"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}),
    ]
    with (
        patch(LITELLM_STREAM, return_value=_iter_mock(chunks_in)),
        patch.object(
            chts.ClickHouseTraceServer,
            "obj_read",
            return_value=tsi.ObjReadRes(obj=prompt_obj),
        ) as mock_obj_read,
    ):
        req = _completion_req(
            project_id, track=False, prompt=_prompt_uri(project_id, "test-prompt")
        )
        chunks = list(streaming_server.completions_create_stream(req))
    assert len(chunks) == 2
    assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
    assert chunks[1]["choices"][0]["finish_reason"] == "stop"
    mock_obj_read.assert_called_once()


def test_streaming_with_prompt_and_template_vars(streaming_server):
    """Template vars are substituted into the resolved prompt before the litellm call."""
    project_id = "test-project"
    prompt_obj = _messages_prompt_obj(
        project_id,
        [
            {"role": "system", "content": "You are {assistant_name}."},
            {"role": "user", "content": "Tell me about {topic}."},
        ],
    )
    chunks_in = [
        _delta_chunk("Mathematics"),
        _stop_chunk({"prompt_tokens": 15, "completion_tokens": 1, "total_tokens": 16}),
    ]
    with (
        patch(LITELLM_STREAM, return_value=_iter_mock(chunks_in)) as mock_litellm,
        patch.object(
            chts.ClickHouseTraceServer,
            "obj_read",
            return_value=tsi.ObjReadRes(obj=prompt_obj),
        ),
    ):
        req = tsi.CompletionsCreateReq(
            project_id=project_id,
            inputs=tsi.CompletionsCreateRequestInputs(
                model="gpt-3.5-turbo",
                messages=[],
                prompt=_prompt_uri(project_id, "test-prompt"),
                template_vars={"assistant_name": "MathBot", "topic": "mathematics"},
            ),
            track_llm_call=False,
        )
        chunks = list(streaming_server.completions_create_stream(req))
    assert len(chunks) == 2
    assert chunks[0]["choices"][0]["delta"]["content"] == "Mathematics"
    mock_litellm.assert_called_once()
    messages = mock_litellm.call_args[1]["inputs"].messages
    assert messages == [
        {"role": "system", "content": "You are MathBot."},
        {"role": "user", "content": "Tell me about mathematics."},
    ]


@pytest.mark.disable_logging_error_check
def test_streaming_with_prompt_error(streaming_server):
    """A failed prompt resolution yields a single error chunk instead of raising."""
    project_id = "test-project"
    with patch.object(
        chts.ClickHouseTraceServer,
        "obj_read",
        side_effect=NotFoundError("Prompt not found"),
    ):
        req = _completion_req(
            project_id, track=False, prompt=_prompt_uri(project_id, "missing-prompt")
        )
        chunks = list(streaming_server.completions_create_stream(req))
    assert len(chunks) == 1
    assert "error" in chunks[0]
    assert "Failed to resolve and apply prompt" in chunks[0]["error"]


# --- resolve_and_apply_prompt --------------------------------------------------


def test_resolve_and_apply_prompt_with_all_params():
    """Prompt + user messages combine and all non-assistant messages get template vars."""
    project_id = "test-project"
    prompt_obj = _messages_prompt_obj(
        project_id,
        [
            {"role": "system", "content": "You are {assistant_name}."},
            {"role": "user", "content": "Answer in {language}."},
        ],
    )
    combined, initial = resolve_and_apply_prompt(
        prompt=_prompt_uri(project_id, "test-prompt"),
        messages=[{"role": "user", "content": "My question: {question}"}],
        template_vars={
            "assistant_name": "TestBot",
            "language": "Spanish",
            "question": "What is 2+2?",
        },
        project_id=project_id,
        obj_read_func=lambda req: tsi.ObjReadRes(obj=prompt_obj),
    )
    assert combined == [
        {"role": "system", "content": "You are TestBot."},
        {"role": "user", "content": "Answer in Spanish."},
        {"role": "user", "content": "My question: What is 2+2?"},
    ]
    assert initial == [{"role": "user", "content": "My question: {question}"}]


def test_resolve_and_apply_prompt_only_prompt_no_template_vars():
    """A prompt with no user messages or vars passes its messages through unchanged."""
    project_id = "test-project"
    prompt_obj = _messages_prompt_obj(
        project_id, [{"role": "system", "content": "You are a helpful assistant."}]
    )
    combined, initial = resolve_and_apply_prompt(
        prompt=_prompt_uri(project_id, "test-prompt"),
        messages=None,
        template_vars=None,
        project_id=project_id,
        obj_read_func=lambda req: tsi.ObjReadRes(obj=prompt_obj),
    )
    assert combined == [{"role": "system", "content": "You are a helpful assistant."}]
    assert initial == []


def test_resolve_and_apply_prompt_only_messages_and_template_vars():
    """With no prompt, user messages get vars applied while initial stays raw."""
    combined, initial = resolve_and_apply_prompt(
        prompt=None,
        messages=[
            {"role": "system", "content": "You are {assistant_name}."},
            {"role": "user", "content": "Hello {user_name}!"},
        ],
        template_vars={"assistant_name": "ChatBot", "user_name": "Alice"},
        project_id="test-project",
        obj_read_func=_unused_obj_read,
    )
    assert combined == [
        {"role": "system", "content": "You are ChatBot."},
        {"role": "user", "content": "Hello Alice!"},
    ]
    assert initial[0]["content"] == "You are {assistant_name}."


def test_resolve_and_apply_prompt_only_messages_no_template_vars():
    """User messages with no prompt or vars pass through unchanged."""
    user_messages = [{"role": "user", "content": "Hello!"}]
    combined, initial = resolve_and_apply_prompt(
        prompt=None,
        messages=user_messages,
        template_vars=None,
        project_id="test-project",
        obj_read_func=_unused_obj_read,
    )
    assert combined == [{"role": "user", "content": "Hello!"}]
    assert initial == user_messages


@pytest.mark.parametrize(
    "template_vars",
    [None, {"name": "Alice"}],
    ids=["empty_inputs", "template_vars_no_messages"],
)
def test_resolve_and_apply_prompt_empty_message_set(template_vars):
    """No prompt and no messages yields empty output even when template vars are present."""
    combined, initial = resolve_and_apply_prompt(
        prompt=None,
        messages=None,
        template_vars=template_vars,
        project_id="test-project",
        obj_read_func=_unused_obj_read,
    )
    assert combined == []
    assert initial == []


def test_resolve_and_apply_prompt_skips_assistant_messages():
    """Template substitution applies to system/user messages but never assistant ones."""
    combined, _ = resolve_and_apply_prompt(
        prompt=None,
        messages=[
            {"role": "system", "content": "You are {assistant_name}."},
            {"role": "user", "content": "Hello {user_name}!"},
            {"role": "assistant", "content": '{"response": "My name is ChatBot."}'},
            {"role": "user", "content": "Yes, my name is {user_name}."},
        ],
        template_vars={"assistant_name": "ChatBot", "user_name": "Alice"},
        project_id="test-project",
        obj_read_func=_unused_obj_read,
    )
    assert combined == [
        {"role": "system", "content": "You are ChatBot."},
        {"role": "user", "content": "Hello Alice!"},
        {"role": "assistant", "content": '{"response": "My name is ChatBot."}'},
        {"role": "user", "content": "Yes, my name is Alice."},
    ]


def test_resolve_and_apply_prompt_prompt_not_found():
    """A missing prompt reference raises NotFoundError."""
    project_id = "test-project"

    def obj_read(req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        raise NotFoundError(f"Object not found: {req.object_id}")

    with pytest.raises(NotFoundError, match="Object not found"):
        resolve_and_apply_prompt(
            prompt=_prompt_uri(project_id, "missing-prompt"),
            messages=None,
            template_vars=None,
            project_id=project_id,
            obj_read_func=obj_read,
        )


def test_resolve_and_apply_prompt_invalid_prompt_type():
    """A non-Prompt prompt reference raises InvalidRequest."""
    project_id = "test-project"
    obj = _model_obj(project_id, "test-obj")
    with pytest.raises(InvalidRequest, match="is not a Prompt or MessagesPrompt"):
        resolve_and_apply_prompt(
            prompt=_prompt_uri(project_id, "test-obj"),
            messages=None,
            template_vars=None,
            project_id=project_id,
            obj_read_func=lambda req: tsi.ObjReadRes(obj=obj),
        )


# --- non-streaming completions write agent spans -------------------------------


def test_completions_writes_agent_span(
    completions_mock_server, completions_secret_fetcher, completions_mock_response
):
    """completions_create writes one span carrying model, tokens, OK status, and ids."""
    with (
        patch(
            LITELLM_COMPLETION,
            return_value=MagicMock(response=completions_mock_response),
        ),
        patch(AGENT_WRITER) as writer_cls,
    ):
        writer = writer_cls.return_value
        result = completions_mock_server.completions_create(
            _completion_req("dGVzdF9wcm9qZWN0", track=True)
        )
    writer.insert_span.assert_called_once()
    assert result.weave_call_id is not None
    assert result.span_id is not None
    assert result.trace_id is not None
    assert result.response["choices"][0]["message"]["content"] == "Hello!"
    span = writer.insert_span.call_args[0][0]
    assert span.project_id == "dGVzdF9wcm9qZWN0"
    assert span.request_model == "gpt-3.5-turbo"
    assert span.input_tokens == 10
    assert span.output_tokens == 5
    assert span.status_code == "OK"


def test_completions_handles_error_response(
    completions_mock_server, completions_secret_fetcher
):
    """An error response is surfaced and recorded as an ERROR span."""
    error_response = {"error": "Rate limit exceeded", "choices": []}
    with (
        patch(LITELLM_COMPLETION, return_value=MagicMock(response=error_response)),
        patch(AGENT_WRITER) as writer_cls,
    ):
        writer = writer_cls.return_value
        result = completions_mock_server.completions_create(
            _completion_req("dGVzdF9wcm9qZWN0", track=True)
        )
    assert result.response["error"] == "Rate limit exceeded"
    writer.insert_span.assert_called_once()
    span = writer.insert_span.call_args[0][0]
    assert span.status_code == "ERROR"
    assert span.status_message == "Rate limit exceeded"


def test_streaming_completions_writes_agent_spans(
    completions_mock_server, completions_secret_fetcher
):
    """Streaming with tracking writes an open (UNSET) span then a completed (OK) span."""
    chunks_in = [
        _delta_chunk("Hi"),
        _stop_chunk({"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}),
    ]
    with (
        patch(LITELLM_STREAM, return_value=_iter_mock(chunks_in)),
        patch(AGENT_WRITER) as writer_cls,
    ):
        writer = writer_cls.return_value
        chunks = list(
            completions_mock_server.completions_create_stream(
                _completion_req("dGVzdF9wcm9qZWN0", track=True)
            )
        )
    assert "_meta" in chunks[0]
    assert "weave_call_id" in chunks[0]["_meta"]
    assert "span_id" in chunks[0]["_meta"]
    assert "trace_id" in chunks[0]["_meta"]
    assert writer.insert_span.call_count == 2
    assert writer.insert_span.call_args_list[0][0][0].status_code == "UNSET"
    completed_span = writer.insert_span.call_args_list[1][0][0]
    assert completed_span.status_code == "OK"
    assert completed_span.project_id == "dGVzdF9wcm9qZWN0"


def test_streaming_completions_error_writes_error_span(
    completions_mock_server, completions_secret_fetcher
):
    """A mid-stream exception is captured in the completed span as an ERROR."""

    def _error_stream():
        yield _delta_chunk("Hi")
        raise RuntimeError("stream died")

    with (
        patch(LITELLM_STREAM, return_value=_error_stream()),
        patch(AGENT_WRITER) as writer_cls,
    ):
        writer = writer_cls.return_value
        list(
            completions_mock_server.completions_create_stream(
                _completion_req("dGVzdF9wcm9qZWN0", track=True)
            )
        )
    assert writer.insert_span.call_count == 2
    completed_span = writer.insert_span.call_args_list[1][0][0]
    assert completed_span.status_code == "ERROR"
    assert "stream died" in completed_span.status_message


# --- provider base_url / header validation -------------------------------------


def test_provider_base_url_validation():
    """Provider.base_url only accepts well-formed, public HTTP(S) URLs and safe headers."""
    assert (
        _make_provider("https://api.openai.com/v1").base_url
        == "https://api.openai.com/v1"
    )
    assert (
        _make_provider("http://my-ollama-server.example.com:11434").base_url
        == "http://my-ollama-server.example.com:11434"
    )

    for bad_url in (
        "ftp://bad.example.com",
        "file:///etc/passwd",
        "https://api.example.com/v1?foo=bar",
        "https://api.example.com/v1#section",
        "http://10.0.0.1/path?",
    ):
        with pytest.raises(ValidationError):
            _make_provider(bad_url)

    for hostname in (
        "metadata.google.internal",
        "metadata.google.internal.",
        "foo.metadata.google.internal",
        "169.254.169.254",
    ):
        with pytest.raises(ValidationError):
            _make_provider(f"http://{hostname}/v1")

    for addr in ("10.0.0.1", "172.16.0.1", "192.168.1.1", "127.0.0.1"):
        with pytest.raises(ValidationError):
            _make_provider(f"http://{addr}/v1")

    for alt_ip in ("0xa9fea9fe", "2852039166", "0x7f000001", "0"):
        with pytest.raises(ValidationError):
            _make_provider(f"http://{alt_ip}/v1")

    with pytest.raises(ValidationError):
        _make_provider("http://[::1]/v1")
    with pytest.raises(ValidationError):
        _make_provider("http://[::ffff:169.254.169.254]/v1")

    for blocked in ("Metadata-Flavor", "METADATA-FLAVOR", "X-aws-ec2-metadata-token"):
        with pytest.raises(ValidationError):
            _make_provider("https://api.example.com", extra_headers={blocked: "val"})

    allowed = _make_provider(
        "https://api.example.com",
        extra_headers={"X-Custom-Header": "value", "Authorization": "Bearer tok"},
    )
    assert "X-Custom-Header" in allowed.extra_headers

    # Validation also runs on assignment, not just init.
    p = _make_provider("https://api.example.com")
    with pytest.raises(ValidationError):
        p.base_url = "http://169.254.169.254/v1"
    with pytest.raises(ValidationError):
        p.extra_headers = {"Metadata-Flavor": "Google"}


# --- custom provider cache -----------------------------------------------------


@pytest.mark.parametrize(
    (
        "override_project",
        "expected_obj_reads",
        "expected_secret_fetches",
        "same_instance",
    ),
    [
        (False, 2, 1, True),  # same key on second call -> cache hit
        (True, 4, 2, False),  # distinct project_id -> distinct cache key
    ],
    ids=["cache_hit_within_ttl", "distinct_keys_isolate"],
)
def test_get_custom_provider_info_cache_behavior(
    custom_provider_fixture,
    override_project,
    expected_obj_reads,
    expected_secret_fetches,
    same_instance,
):
    """Cache hits within TTL skip resolution; distinct keys do not collide."""
    project_id, provider_id, model_object_id, obj_read, secret_fetcher = (
        custom_provider_fixture
    )
    first = get_custom_provider_info(project_id, provider_id, model_object_id, obj_read)
    second_project = "other-project" if override_project else project_id
    second = get_custom_provider_info(
        second_project, provider_id, model_object_id, obj_read
    )
    assert (first is second) is same_instance
    assert obj_read.call_count == expected_obj_reads
    assert secret_fetcher.fetch.call_count == expected_secret_fetches


def test_get_custom_provider_info_requires_secret_fetcher_on_cache_hit(
    custom_provider_fixture,
):
    """A cache hit must not bypass the secret_fetcher-required guard."""
    project_id, provider_id, model_object_id, obj_read, _ = custom_provider_fixture
    get_custom_provider_info(project_id, provider_id, model_object_id, obj_read)

    _secret_fetcher_context.set(None)
    with pytest.raises(InvalidRequest, match="No secret fetcher found"):
        get_custom_provider_info(project_id, provider_id, model_object_id, obj_read)


# --- fixtures ------------------------------------------------------------------


@pytest.fixture
def streaming_server():
    """ClickHouseTraceServer with a stubbed CH client and an OPENAI/CUSTOM/TEST key fetcher."""
    server = _mock_ch_server()
    fetcher = _secret_fetcher(
        {
            "OPENAI_API_KEY": "test-api-key-value",
            "CUSTOM_API_KEY": "test-api-key-value",
            "TEST_API_KEY": "test-api-key-value",
        }
    )
    token = _secret_fetcher_context.set(fetcher)
    yield server
    _secret_fetcher_context.reset(token)


@pytest.fixture
def completions_mock_server():
    """ClickHouseTraceServer with a stubbed CH client for completions tests."""
    return _mock_ch_server()


@pytest.fixture
def completions_secret_fetcher():
    """Set up a mock secret fetcher with the OPENAI test key."""
    fetcher = _secret_fetcher({"OPENAI_API_KEY": "test-api-key-value"})
    token = _secret_fetcher_context.set(fetcher)
    yield fetcher
    _secret_fetcher_context.reset(token)


@pytest.fixture
def completions_mock_response():
    """Standard mock LLM response for completions tests."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-3.5-turbo",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.fixture
def custom_provider_fixture():
    """Provider/model/secret fixture for cache tests.

    Yields (project_id, provider_id, model_object_id, mock_obj_read, mock_secret_fetcher).
    """
    project_id = "p"
    provider_id = "prov"
    model_object_id = f"{provider_id}-mdl"
    provider_obj = _provider_obj(project_id, provider_id, digest="d1", extra_headers={})
    model_obj = _provider_model_obj(
        project_id, model_object_id, provider_id, digest="d2", name="actual-model"
    )
    obj_read = MagicMock(
        side_effect=_obj_read_router(
            {provider_id: provider_obj, model_object_id: model_obj}
        )
    )
    secret_fetcher = _secret_fetcher({"TEST_API_KEY": "k"})
    token = _secret_fetcher_context.set(secret_fetcher)
    try:
        yield project_id, provider_id, model_object_id, obj_read, secret_fetcher
    finally:
        _secret_fetcher_context.reset(token)


# --- helpers -------------------------------------------------------------------


def _mock_ch_server() -> chts.ClickHouseTraceServer:
    server = chts.ClickHouseTraceServer(host="test_host")
    mock_ch_client = MagicMock()
    mock_ch_client.query.return_value = MagicMock(result_rows=[[0, 0]])
    # ch_client is lazy; pre-populating _thread_local.ch_client bypasses _mint_client.
    server._thread_local.ch_client = mock_ch_client
    return server


def _secret_fetcher(secrets: dict[str, str]) -> MagicMock:
    fetcher = MagicMock()
    fetcher.fetch.return_value = {"secrets": secrets}
    return fetcher


def _obj_read_router(
    objs: dict[str, tsi.ObjSchema], default: tsi.ObjSchema | None = None
) -> Callable[[tsi.ObjReadReq], tsi.ObjReadRes]:
    """Return an obj_read side-effect that maps object_id -> ObjReadRes."""

    def _read(req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        obj = objs.get(req.object_id)
        if obj is not None:
            return tsi.ObjReadRes(obj=obj)
        if default is not None:
            return tsi.ObjReadRes(obj=default)
        raise NotFoundError(f"Unknown object_id: {req.object_id}")

    return _read


def _unused_obj_read(req: tsi.ObjReadReq) -> tsi.ObjReadRes:
    raise NotImplementedError("Should not be called")


def _obj_schema(project_id: str, object_id: str, **kwargs) -> tsi.ObjSchema:
    base = {
        "project_id": project_id,
        "object_id": object_id,
        "created_at": datetime.datetime.now(),
        "version_index": 1,
        "is_latest": 1,
        "kind": "object",
        "deleted_at": None,
    }
    base.update(kwargs)
    return tsi.ObjSchema(**base)


def _provider_obj(
    project_id: str,
    object_id: str,
    *,
    digest: str = "digest-1",
    base_url: str = "https://api.example.com",
    api_key_name: str = "TEST_API_KEY",
    extra_headers: dict | None = None,
    extra_val: dict | None = None,
) -> tsi.ObjSchema:
    val = {
        "base_url": base_url,
        "api_key_name": api_key_name,
        "extra_headers": {"X-Header": "value"}
        if extra_headers is None
        else extra_headers,
        "return_type": "openai",
    }
    if extra_val:
        val.update(extra_val)
    return _obj_schema(
        project_id,
        object_id,
        digest=digest,
        base_object_class="Provider",
        leaf_object_class="Provider",
        val=val,
    )


def _provider_model_obj(
    project_id: str,
    object_id: str,
    provider_id: str,
    *,
    digest: str = "digest-2",
    name: str = "actual-model-name",
) -> tsi.ObjSchema:
    return _obj_schema(
        project_id,
        object_id,
        digest=digest,
        base_object_class="ProviderModel",
        leaf_object_class="ProviderModel",
        val={"name": name, "provider": provider_id, "max_tokens": 4096, "mode": "chat"},
    )


def _messages_prompt_obj(project_id: str, messages: list[dict]) -> tsi.ObjSchema:
    return _obj_schema(
        project_id,
        "test-prompt",
        digest="digest-1",
        base_object_class="MessagesPrompt",
        leaf_object_class="MessagesPrompt",
        val={"messages": messages},
    )


def _model_obj(project_id: str, object_id: str) -> tsi.ObjSchema:
    return _obj_schema(
        project_id,
        object_id,
        digest="digest-1",
        base_object_class="Model",
        leaf_object_class="Model",
        val={"name": "test"},
    )


def _prompt_uri(project_id: str, object_id: str) -> str:
    return f"weave-trace-internal:///{project_id}/object/{object_id}:digest-1"


def _completion_req(
    project_id: str,
    *,
    track: bool,
    model: str = "gpt-3.5-turbo",
    prompt: str | None = None,
) -> tsi.CompletionsCreateReq:
    inputs_kwargs: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello"}],
    }
    if prompt is not None:
        inputs_kwargs["messages"] = [{"role": "user", "content": "Hi"}]
        inputs_kwargs["prompt"] = prompt
    return tsi.CompletionsCreateReq(
        project_id=project_id,
        inputs=tsi.CompletionsCreateRequestInputs(**inputs_kwargs),
        track_llm_call=track,
    )


def _delta_chunk(content: str, *, model: str = "test-model") -> dict:
    return {
        "choices": [{"delta": {"content": content}, "finish_reason": None, "index": 0}],
        "id": "test-id",
        "model": model,
        "created": 1234567890,
    }


def _stop_chunk(usage: dict, *, model: str = "test-model") -> dict:
    return {
        "choices": [{"delta": {}, "finish_reason": "stop", "index": 0}],
        "id": "test-id",
        "model": model,
        "created": 1234567890,
        "usage": usage,
    }


def _iter_mock(chunks: list[dict]) -> MagicMock:
    stream = MagicMock()
    stream.__iter__.return_value = chunks
    return stream


def _make_provider(base_url: str, extra_headers: dict | None = None) -> Provider:
    return Provider(
        name="test",
        base_url=base_url,
        api_key_name="MY_KEY",
        extra_headers=extra_headers or {},
    )
