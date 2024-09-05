import importlib
import typing
from functools import wraps

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if typing.TYPE_CHECKING:
    from cohere.types.non_streamed_chat_response import NonStreamedChatResponse


def cohere_accumulator(
    acc: typing.Optional[dict],
    value: typing.Any,
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


def cohere_wrapper(name: str) -> typing.Callable:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


def cohere_wrapper_v2(name: str) -> typing.Callable:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        def _post_process_response(fn: typing.Callable) -> typing.Any:
            @wraps(fn)
            def _wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
                response = fn(*args, **kwargs)
                
                try:
                    from cohere.v2.types.non_streamed_chat_response2 import NonStreamedChatResponse2
                    from cohere.v2.types.usage import Usage

                    # Create a new instance with modified `usage`
                    response_dict = response.dict()
                    response_dict["usage"] = Usage(
                        billed_units=response.model_extra["meta"]["billed_units"],
                        tokens=response.model_extra["meta"]["tokens"],
                    )
                    response = NonStreamedChatResponse2(**response_dict)
                except:
                    pass # prompt to upgrade cohere sdk

                return response

            return _wrapper

        op = weave.op()(_post_process_response(fn))
        op.name = name  # type: ignore
        return op

    return wrapper


def cohere_stream_wrapper(name: str) -> typing.Callable:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return add_accumulator(op, lambda inputs: cohere_accumulator)  # type: ignore

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
            cohere_wrapper_v2("cohere.AsyncClientV2.chat"),
        ),
    ]
)
