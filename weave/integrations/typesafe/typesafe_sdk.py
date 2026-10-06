"""Spans for TypeSafe ``system_one`` calls.

One call becomes one provider chat span. This integration does not create a
Weave Call. ``weave.parent_call.*`` on a surrounding ``@weave.op`` is a link
to that call, not an OTel parent. Do not enable this together with another
TypeSafe instrumentor; pick one.
"""

from __future__ import annotations

import importlib
import inspect
import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from weave.conversation import (
    LLM,
    Message,
    TextPart,
    Turn,
    Usage,
    get_current_conversation,
    get_current_turn,
)
from weave.integrations.integration_metadata import library_integration
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.settings import should_redact_pii
from weave.utils.pii_redaction import redact_pii_string

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "typesafe"
_AGENT_NAME = "typesafe SDK"
_OPERATION = "typesafe.system_one"
_QUESTIONS_ATTR = "typesafe.questions"
_REQUEST_ID_HEADER = "x-typesafe-request-id"
_CAPTURE_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
_CAPTURE_OFF = {"0", "false", "no", "off"}

_INTEGRATION_ATTRS = library_integration(
    _PROVIDER_NAME, distribution_name="typesafe-sdk"
).as_otel_attributes()

_typesafe_patcher: MultiPatcher | None = None
_capture_content_override: bool | None = None


def set_capture_content(capture_content: bool | None) -> None:
    """Set the process default for this integration.

    ``None`` clears an earlier override and the environment variable applies
    again. A surrounding conversation with ``include_content=False`` still
    drops content.
    """
    global _capture_content_override  # noqa: PLW0603
    _capture_content_override = capture_content


def _process_capture_content() -> bool:
    if _capture_content_override is not None:
        return _capture_content_override
    raw = os.environ.get(_CAPTURE_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in _CAPTURE_OFF


def _effective_capture() -> bool:
    if not _process_capture_content():
        return False
    conversation = get_current_conversation()
    if conversation is not None and not conversation.include_content:
        return False
    return True


def _sync_client() -> Any:
    # Optional dependency: absent until the user installs typesafe-sdk.
    return importlib.import_module("typesafe_sdk").TypeSafeClient


def _async_client() -> Any:
    # Optional dependency: absent until the user installs typesafe-sdk.
    return importlib.import_module("typesafe_sdk").AsyncTypeSafeClient


def _error_type(exc: BaseException) -> str:
    error_class = type(exc)
    name = error_class.__qualname__
    if error_class.__module__ != "builtins":
        return f"{error_class.__module__}.{name}"
    return name


def _error_request_id(exc: BaseException) -> str | None:
    headers = getattr(exc, "headers", None)
    getter = getattr(headers, "get", None)
    if getter is None:
        return None
    try:
        value = getter(_REQUEST_ID_HEADER)
    except Exception:
        return None
    if isinstance(value, str) and value:
        return value
    return None


def _stamp_error(span_obj: Any, exc: BaseException) -> None:
    """Mark a span failed without copying the provider error text.

    ``TypeSafeAPIError`` stringifies the response body. ``record_error`` would
    put that text on the status and on an exception event, so spans this
    integration closes set status with no description and skip
    ``record_exception``.
    """
    otel_span = getattr(span_obj, "_otel_span", None)
    if otel_span is None or not otel_span.is_recording():
        return
    otel_span.set_attribute("error.type", _error_type(exc))
    otel_span.set_status(Status(StatusCode.ERROR))
    status = getattr(exc, "status", None)
    if isinstance(status, int) and not isinstance(status, bool):
        otel_span.set_attribute("http.response.status_code", status)
    request_id = _error_request_id(exc)
    if request_id is not None:
        otel_span.set_attribute("gen_ai.response.id", request_id)


def _stamp_provenance(span_obj: Any) -> None:
    span_obj.set_attributes(
        {**_INTEGRATION_ATTRS, "weave.integration.operation": _OPERATION}
    )


def _started_turn() -> Turn | None:
    turn = get_current_turn()
    if turn is None or getattr(turn, "_ended", True):
        return None
    if getattr(turn, "_otel_span", None) is None:
        return None
    return turn


def _ambient_parent() -> Any | None:
    span = otel_trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid or not span_context.trace_flags.sampled:
        return None
    if span_context.is_remote or span.is_recording():
        return otel_trace.set_span_in_context(span)
    return None


def _effective_body(
    client: Any,
    state: Any,
    questions: Any,
    model: Any,
    extra_body: Any,
) -> dict[str, Any]:
    config = getattr(client, "_config", None)
    default_model = getattr(config, "default_model", None) or "jev-latest"
    body: dict[str, Any] = {
        "state": state,
        "model": default_model if model is None else model,
        "questions": questions,
    }
    if isinstance(extra_body, Mapping):
        body.update(extra_body)
    return body


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _state_message(state: Any) -> Message:
    if isinstance(state, str):
        return Message(role="user", content=state)
    return Message(
        role="user",
        parts=[TextPart(content=json.dumps(_jsonable(state), sort_keys=True))],
    )


def _question_wire(question: Any) -> dict[str, Any]:
    dumped = _jsonable(question)
    if isinstance(dumped, dict):
        return dumped
    return {"value": dumped}


def _questions_json(questions: Any) -> str | None:
    if isinstance(questions, Mapping):
        items = [
            {"id": key, **_question_wire(question)}
            for key, question in questions.items()
        ]
    elif isinstance(questions, Sequence) and not isinstance(questions, (str, bytes)):
        items = [
            {"id": index, **_question_wire(question)}
            for index, question in enumerate(questions)
        ]
    else:
        return None
    raw = json.dumps(items)
    if should_redact_pii():
        return redact_pii_string(raw)
    return raw


def _answers_message(result: Any) -> Message | None:
    answers = getattr(result, "answers", None)
    if answers is None and isinstance(result, Mapping):
        answers = result.get("answers")
    if answers is None:
        return None
    return Message(
        role="assistant",
        parts=[TextPart(content=json.dumps(_jsonable(answers), sort_keys=True))],
    )


def _usage_from(result: Any) -> Usage | None:
    usage = getattr(result, "usage", None)
    if usage is None and isinstance(result, Mapping):
        usage = result.get("usage")
    if usage is None:
        return None
    if isinstance(usage, Mapping):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
    if not isinstance(input_tokens, int) and not isinstance(output_tokens, int):
        return None
    return Usage(
        input_tokens=input_tokens if isinstance(input_tokens, int) else 0,
        output_tokens=output_tokens if isinstance(output_tokens, int) else 0,
    )


def _response_model_name(result: Any) -> str | None:
    model = getattr(result, "model", None)
    if not isinstance(model, str) and isinstance(result, Mapping):
        model = result.get("model")
    if isinstance(model, str) and model:
        return model
    return None


def _request_id(result: Any) -> str | None:
    try:
        request_id = result.request_id
    except Exception:
        return None
    if isinstance(request_id, str) and request_id:
        return request_id
    return None


@dataclass
class _Trace:
    llm: LLM
    turn: Turn | None
    owns_turn: bool
    capture: bool
    closed: bool = False


def _open_trace(
    client: Any, state: Any, questions: Any, kwargs: Mapping[str, Any]
) -> _Trace | None:
    turn: Turn | None = None
    owns_turn = False
    llm: LLM | None = None
    try:
        capture = _effective_capture()
        body = _effective_body(
            client,
            state,
            questions,
            kwargs.get("model"),
            kwargs.get("extra_body"),
        )
        model_name = body.get("model")
        if not isinstance(model_name, str):
            model_name = ""
        turn = _started_turn()
        parent = None if turn is not None else _ambient_parent()
        if turn is None and parent is None:
            turn = Turn(agent_name=_AGENT_NAME)
            # __exit__ would copy the provider error text onto the span.
            turn.__enter__()  # noqa: PLC2801
            owns_turn = True
        if turn is not None:
            llm = turn.start_llm(model=model_name, provider_name=_PROVIDER_NAME)
        else:
            llm = LLM(model=model_name, provider_name=_PROVIDER_NAME)
            # No Turn to thread through start_llm. The ambient span is the parent.
            llm._parent_otel_context = parent
        if capture:
            llm.input_messages = [_state_message(body.get("state"))]
        # Same as the turn: leave the span with end(), not __exit__.
        llm.__enter__()  # noqa: PLC2801
        _stamp_provenance(llm)
        if owns_turn and turn is not None:
            _stamp_provenance(turn)
        if capture:
            questions_json = _questions_json(body.get("questions"))
            if questions_json is not None:
                llm.set_attributes({_QUESTIONS_ATTR: questions_json})
        return _Trace(llm=llm, turn=turn, owns_turn=owns_turn, capture=capture)
    except Exception:
        logger.warning("TypeSafe span setup failed", exc_info=True)
        if llm is not None and not llm._ended:
            llm.end()
        if owns_turn and turn is not None and not turn._ended:
            turn.end()
        return None


def _fill(trace: _Trace, result: Any) -> None:
    record: dict[str, Any] = {"output_type": "json"}
    response_model = _response_model_name(result)
    if response_model is not None:
        record["response_model"] = response_model
    usage = _usage_from(result)
    if usage is not None:
        record["usage"] = usage
    request_id = _request_id(result)
    if request_id is not None:
        record["response_id"] = request_id
    if trace.capture:
        answers = _answers_message(result)
        if answers is not None:
            record["output_messages"] = [answers]
    trace.llm.record(**record)


def _close(trace: _Trace, exc: BaseException | None) -> None:
    if trace.closed:
        return
    trace.closed = True
    if exc is not None:
        _stamp_error(trace.llm, exc)
        if trace.owns_turn and trace.turn is not None:
            _stamp_error(trace.turn, exc)
    if not trace.llm._ended:
        trace.llm.end()
    if trace.owns_turn and trace.turn is not None and not trace.turn._ended:
        trace.turn.end()


def _trace_call(
    original: Any, client: Any, state: Any, questions: Any, kwargs: Any
) -> Any:
    trace = _open_trace(client, state, questions, kwargs)
    if trace is None:
        return original(client, state, questions, **kwargs)
    try:
        result = original(client, state, questions, **kwargs)
    except BaseException as exc:
        _close(trace, exc)
        raise
    try:
        _fill(trace, result)
    except Exception:
        logger.warning("TypeSafe span capture failed", exc_info=True)
    _close(trace, None)
    return result


async def _trace_call_async(
    original: Any, client: Any, state: Any, questions: Any, kwargs: Any
) -> Any:
    trace = _open_trace(client, state, questions, kwargs)
    if trace is None:
        return await original(client, state, questions, **kwargs)
    try:
        result = await original(client, state, questions, **kwargs)
    except BaseException as exc:
        _close(trace, exc)
        raise
    try:
        _fill(trace, result)
    except Exception:
        logger.warning("TypeSafe span capture failed", exc_info=True)
    _close(trace, None)
    return result


def _make_wrapper(original: Any) -> Any:
    if inspect.iscoroutinefunction(original):

        async def async_wrapper(
            self: Any, state: Any, questions: Any, **kwargs: Any
        ) -> Any:
            return await _trace_call_async(original, self, state, questions, kwargs)

        return async_wrapper

    def wrapper(self: Any, state: Any, questions: Any, **kwargs: Any) -> Any:
        return _trace_call(original, self, state, questions, kwargs)

    return wrapper


def get_typesafe_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()
    if not settings.enabled:
        return NoOpPatcher()

    global _typesafe_patcher  # noqa: PLW0603
    if _typesafe_patcher is not None:
        return _typesafe_patcher

    _typesafe_patcher = MultiPatcher(
        [
            SymbolPatcher(_sync_client, "system_one", _make_wrapper),
            SymbolPatcher(_async_client, "system_one", _make_wrapper),
        ]
    )
    return _typesafe_patcher
