from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from cohere.types.assistant_message_response import AssistantMessageResponse
from cohere.types.assistant_message_response_content_item import (
    TextAssistantMessageResponseContentItem,
)
from cohere.types.non_streamed_chat_response import NonStreamedChatResponse
from cohere.types.usage import Usage
from cohere.v2.types.v2chat_response import V2ChatResponse

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    pass


_cohere_patcher: MultiPatcher | None = None


def cohere_accumulator(acc: dict | None, value: Any) -> NonStreamedChatResponse:
    # don't need to accumulate, is build-in by cohere!
    # https://docs.cohere.com/docs/streaming
    # A stream-end event is the final event of the stream, and is returned only when streaming is finished.
    # This event contains aggregated data from all the other events such as the complete text,
    # as well as a finish_reason for why the stream ended (i.e. because of it was finished or there was an error).
    if acc is None:
        acc = {}

    # we wait for the last event
    if (
        hasattr(value, "event_type")
        and value.event_type == "stream-end"
        and value.is_finished
        and value.response
    ):
        acc = value.response
    return acc


def cohere_accumulator_v2(acc: V2ChatResponse | None, value: Any) -> V2ChatResponse:
    if acc is None:
        # Initialize accumulator with basic structure
        acc = V2ChatResponse(
            id=value.id if hasattr(value, "id") else "",
            finish_reason=None,
            message=AssistantMessageResponse(
                role="assistant",
                tool_calls=None,
                tool_plan=None,
                content=[],
                citations=None,
            ),
            usage=None,
        )

    if value is None:
        return acc

    if value.type == "message-start":
        if hasattr(value, "id"):
            acc.id = value.id
        if (
            hasattr(value, "delta")
            and hasattr(value.delta, "message")
            and hasattr(value.delta.message, "role")
        ):
            acc.message.role = value.delta.message.role

    elif value.type == "content-start":
        if (
            hasattr(value, "delta")
            and hasattr(value.delta, "message")
            and hasattr(value.delta.message, "content")
            and hasattr(value.delta.message.content, "type")
            and value.delta.message.content.type == "text"
        ):
            # Add new text content item
            text_item = TextAssistantMessageResponseContentItem(
                type="text",
                text=value.delta.message.content.text or "",
            )
            acc.message.content.append(text_item)  # type: ignore

    elif value.type == "content-delta":
        if (
            hasattr(value, "index")
            and hasattr(value, "delta")
            and hasattr(value.delta, "message")
            and hasattr(value.delta.message, "content")
            and hasattr(value.delta.message.content, "text")
            and value.index < len(acc.message.content)  # type: ignore
        ):
            current_item = acc.message.content[value.index]  # type: ignore
            if hasattr(current_item, "text"):
                current_item.text += value.delta.message.content.text

    elif value.type == "message-end":
        if hasattr(value, "delta") and hasattr(value.delta, "finish_reason"):
            acc.finish_reason = value.delta.finish_reason
        if hasattr(value, "delta") and hasattr(value.delta, "usage"):
            acc.usage = value.delta.usage

    return acc


def cohere_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def cohere_wrapper_v2(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        def _post_process_response(fn: Callable) -> Any:
            @wraps(fn)
            def _wrapper(*args: Any, **kwargs: Any) -> Any:
                response = fn(*args, **kwargs)

                try:
                    # Extract usage information from meta and populate the usage field
                    if hasattr(response, "meta") and response.meta:
                        response.usage = Usage(
                            billed_units=response.meta.get("billed_units"),
                            tokens=response.meta.get("tokens"),
                        )
                except Exception:
                    pass  # If extraction fails, continue without usage info

                return response

            return _wrapper

        op_kwargs = settings.model_dump()
        op = weave.op(_post_process_response(fn), **op_kwargs)
        return op

    return wrapper


def cohere_wrapper_async_v2(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        def _post_process_response(fn: Callable) -> Any:
            @wraps(fn)
            async def _wrapper(*args: Any, **kwargs: Any) -> Any:
                response = await fn(*args, **kwargs)

                try:
                    # Extract usage information from meta and populate the usage field
                    if hasattr(response, "meta") and response.meta:
                        response.usage = Usage(
                            billed_units=response.meta.get("billed_units"),
                            tokens=response.meta.get("tokens"),
                        )
                except Exception:
                    pass  # If extraction fails, continue without usage info

                return response

            return _wrapper

        op_kwargs = settings.model_dump()
        op = weave.op(_post_process_response(fn), **op_kwargs)
        return op

    return wrapper


def cohere_stream_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(op, lambda inputs: cohere_accumulator)

    return wrapper


def cohere_stream_wrapper_v2(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return _add_accumulator(op, lambda inputs: cohere_accumulator_v2)

    return wrapper


def get_cohere_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _cohere_patcher
    if _cohere_patcher is not None:
        return _cohere_patcher

    base = settings.op_settings

    chat_settings = base.model_copy(update={"name": base.name or "cohere.Client.chat"})
    async_chat_settings = base.model_copy(
        update={"name": base.name or "cohere.AsyncClient.chat"}
    )
    chat_stream_settings = base.model_copy(
        update={"name": base.name or "cohere.Client.chat_stream"}
    )
    async_chat_stream_settings = base.model_copy(
        update={"name": base.name or "cohere.AsyncClient.chat_stream"}
    )
    chat_v2_settings = base.model_copy(
        update={"name": base.name or "cohere.ClientV2.chat"}
    )
    async_chat_v2_settings = base.model_copy(
        update={"name": base.name or "cohere.AsyncClientV2.chat"}
    )
    chat_stream_v2_settings = base.model_copy(
        update={"name": base.name or "cohere.ClientV2.chat_stream"}
    )
    async_chat_stream_v2_settings = base.model_copy(
        update={"name": base.name or "cohere.AsyncClientV2.chat_stream"}
    )

    _cohere_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "Client.chat",
                cohere_wrapper(chat_settings),
            ),
            # Patch the async chat method
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "AsyncClient.chat",
                cohere_wrapper(async_chat_settings),
            ),
            # Add patch for chat_stream method
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "Client.chat_stream",
                cohere_stream_wrapper(chat_stream_settings),
            ),
            # Add patch for async chat_stream method
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "AsyncClient.chat_stream",
                cohere_stream_wrapper(async_chat_stream_settings),
            ),
            # Add patch for cohere v2
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "ClientV2.chat",
                cohere_wrapper_v2(chat_v2_settings),
            ),
            # Add patch for cohre v2 async chat method
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "AsyncClientV2.chat",
                cohere_wrapper_async_v2(async_chat_v2_settings),
            ),
            # Add patch for chat_stream method v2
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "ClientV2.chat_stream",
                cohere_stream_wrapper_v2(chat_stream_v2_settings),
            ),
            # Add patch for async chat_stream method v2
            SymbolPatcher(
                lambda: importlib.import_module("cohere"),
                "AsyncClientV2.chat_stream",
                cohere_stream_wrapper_v2(async_chat_stream_v2_settings),
            ),
        ]
    )

    return _cohere_patcher
