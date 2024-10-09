import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if TYPE_CHECKING:
    from cohere.types.non_streamed_chat_response import NonStreamedChatResponse
    from cohere.v2.types.non_streamed_chat_response2 import NonStreamedChatResponse2


def cohere_accumulator(
    acc: Optional[dict],
    value: Any,
) -> "NonStreamedChatResponse":
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


def cohere_accumulator_v2(
    acc: Optional[dict],
    value: Any,
) -> "NonStreamedChatResponse2":
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


def cohere_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


def cohere_wrapper_v2(name: str) -> Callable:
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

        op = weave.op()(_post_process_response(fn))
        op.name = name  # type: ignore
        return op

    return wrapper


def cohere_wrapper_async_v2(name: str) -> Callable:
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

        op = weave.op()(_post_process_response(fn))
        op.name = name  # type: ignore
        return op

    return wrapper


def cohere_stream_wrapper(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(op, lambda inputs: cohere_accumulator)  # type: ignore

    return wrapper


def cohere_stream_wrapper_v2(name: str) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(
            op, make_accumulator=lambda inputs: cohere_accumulator_v2
        )

    return wrapper


cohere_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "Client.chat",
            cohere_wrapper("cohere.Client.chat"),
        ),
        # Patch the async chat method
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "AsyncClient.chat",
            cohere_wrapper("cohere.AsyncClient.chat"),
        ),
        # Add patch for chat_stream method
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "Client.chat_stream",
            cohere_stream_wrapper("cohere.Client.chat_stream"),
        ),
        # Add patch for async chat_stream method
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "AsyncClient.chat_stream",
            cohere_stream_wrapper("cohere.AsyncClient.chat_stream"),
        ),
        # Add patch for cohere v2
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "ClientV2.chat",
            cohere_wrapper_v2("cohere.ClientV2.chat"),
        ),
        # Add patch for cohre v2 async chat method
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "AsyncClientV2.chat",
            cohere_wrapper_async_v2("cohere.AsyncClientV2.chat"),
        ),
        # Add patch for chat_stream method v2
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "ClientV2.chat_stream",
            cohere_stream_wrapper_v2("cohere.ClientV2.chat_stream"),
        ),
        # Add patch for async chat_stream method v2
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "AsyncClientV2.chat_stream",
            cohere_stream_wrapper_v2("cohere.AsyncClientV2.chat_stream"),
        ),
    ]
)
