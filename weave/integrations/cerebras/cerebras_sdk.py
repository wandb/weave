import importlib
import typing
from functools import wraps

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def create_wrapper_sync(
    name: str,
) -> typing.Callable[[typing.Callable], typing.Callable]:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


def create_wrapper_async(
    name: str,
) -> typing.Callable[[typing.Callable], typing.Callable]:
    def wrapper(fn: typing.Callable) -> typing.Callable:
        def _fn_wrapper(fn: typing.Callable) -> typing.Callable:
            @wraps(fn)
            async def _async_wrapper(
                *args: typing.Any, **kwargs: typing.Any
            ) -> typing.Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op = weave.op()(_fn_wrapper(fn))
        op.name = name  # type: ignore
        return op

    return wrapper


cerebras_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("cerebras.cloud.sdk.resources.chat"),
            "CompletionsResource.create",
            create_wrapper_sync(name="cerebras.chat.completions.create"),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("cerebras.cloud.sdk.resources.chat"),
            "AsyncCompletionsResource.create",
            create_wrapper_async(name="cerebras.chat.completions.create"),
        ),
    ]
)
