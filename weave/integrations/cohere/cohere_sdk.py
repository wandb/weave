from __future__ import annotations

import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

if TYPE_CHECKING:
    from cohere.types.non_streamed_chat_response import NonStreamedChatResponse
    from cohere.v2.types.non_streamed_chat_response2 import NonStreamedChatResponse2


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
    if hasattr(value, "event_type"):
        if value.event_type == "stream-end" and value.is_finished:
            if value.response:
                acc = value.response
    return acc


def cohere_accumulator_v2(acc: dict | None, value: Any) -> NonStreamedChatResponse2:
    from cohere.v2.types.assistant_message_response import AssistantMessageResponse
    from cohere.v2.types.non_streamed_chat_response2 import NonStreamedChatResponse2

    def _accumulate_content(
        prev: str,
        content: str,
    ) -> str:
        if isinstance(prev, str) and isinstance(content, str):
            prev += content
        return prev

    if acc is None:
        acc = NonStreamedChatResponse2(
            id=value.id,
            finish_reason=None,
            prompt=None,
            message=AssistantMessageResponse(
                role=value.delta.message.role,
                tool_calls=value.delta.message.tool_calls,
                tool_plan=value.delta.message.tool_plan,
                content=value.delta.message.content,
                citations=value.delta.message.citations,
            ),
            usage=None,
        )

    if value is None:
        return acc

    if value.type == "content-start" and value.delta.message.content.type == "text":
        if len(acc.message.content) == value.index:  # type: ignore
            acc.message.content.append(value.delta.message.content.text)  # type: ignore

    if value.type == "content-delta":
        _content = _accumulate_content(
            acc.message.content[value.index],  # type: ignore
            value.delta.message.content.text,  # type: ignore
        )
        acc.message.content[value.index] = _content  # type: ignore

    if value.type == "message-end":
        acc = acc.copy(  # type: ignore
            update={
                "finish_reason": value.delta.finish_reason,
                "usage": value.delta.usage,
            }
        )

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
                    from cohere.v2.types.non_streamed_chat_response2 import (
                        NonStreamedChatResponse2,
                    )
                    from cohere.v2.types.usage import Usage

                    # Create a new instance with modified `usage`
                    response_dict = response.dict()
                    response_dict["usage"] = Usage(
                        billed_units=response.model_extra["meta"]["billed_units"],
                        tokens=response.model_extra["meta"]["tokens"],
                    )
                    response = NonStreamedChatResponse2(**response_dict)
                except:
                    pass  # prompt to upgrade cohere sdk

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
                    from cohere.v2.types.non_streamed_chat_response2 import (
                        NonStreamedChatResponse2,
                    )
                    from cohere.v2.types.usage import Usage

                    # Create a new instance with modified `usage`
                    response_dict = response.dict()
                    response_dict["usage"] = Usage(
                        billed_units=response.model_extra["meta"]["billed_units"],
                        tokens=response.model_extra["meta"]["tokens"],
                    )
                    response = NonStreamedChatResponse2(**response_dict)
                except:
                    pass  # prompt to upgrade cohere sdk

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
