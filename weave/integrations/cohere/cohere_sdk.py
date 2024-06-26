import importlib
import typing

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import MultiPatcher, SymbolPatcher

if typing.TYPE_CHECKING:
    from cohere.types.non_streamed_chat_response import NonStreamedChatResponse
    from cohere.types.streamed_chat_response import StreamedChatResponse_TextGeneration

def cohere_accumulator(
    acc: typing.Optional[dict],
    value: typing.Any,
) -> dict:
    if acc is None:
        acc = {
            "text": [],
            "generation_id": "",
            "token_count": {"prompt_tokens": 0, "response_tokens": 0, "total_tokens": 0},
            "meta": {},
        }

    if hasattr(value, 'event_type'):
        if value.event_type == "text-generation":
            acc["text"].append(value.text)
            acc["token_count"]["response_tokens"] += 1
            acc["token_count"]["total_tokens"] += 1
        elif value.event_type == "stream-end":
            acc["generation_id"] = getattr(value, 'generation_id', '')
            acc["meta"] = getattr(value, 'meta', {})

    return acc

def cohere_wrapper(name: str) -> typing.Callable:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        op = weave.op()(fn)
        print(f"op: {op}")
        op.name = name # type: ignore
        print(f"op2: {op}")
        return op
    return wrapper

def cohere_stream_wrapper(name: str) -> typing.Callable:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        op = weave.op()(fn)
        op.name = name # type: ignore
        
        @weave.op()
        def finalize_accumulator(acc: dict) -> "NonStreamedChatResponse":
            from cohere.types.non_streamed_chat_response import NonStreamedChatResponse
            return NonStreamedChatResponse(
                text="".join(acc["text"]),
                generation_id=acc["generation_id"],
                token_count=acc["token_count"],
                meta=acc["meta"],
            )
        
        return add_accumulator(op, cohere_accumulator, on_finish_post_processor=finalize_accumulator) # type: ignore
    return wrapper

cohere_patcher = MultiPatcher(
    [
        # Patch the sync chat method
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "Client.chat",
            cohere_wrapper("cohere.Client.chat"),
            # weave.op(),
        ),
        # Patch the async chat method
        SymbolPatcher(
            lambda: importlib.import_module("cohere"),
            "AsyncClient.chat",
            cohere_wrapper("cohere.AsyncClient.chat"),
            # weave.op(),
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
    ]
)
