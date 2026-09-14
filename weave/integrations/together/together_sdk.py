from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import wraps
from typing import Any

import weave
from weave.integrations.integration_metadata import (
    library_integration,
    with_integration_metadata,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_together_patcher: MultiPatcher | None = None
TOGETHER_INTEGRATION = library_integration("together", distribution_name="together")


def create_wrapper_sync(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def create_wrapper_async(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        def _fn_wrapper(fn: Callable) -> Callable:
            @wraps(fn)
            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await fn(*args, **kwargs)

            return _async_wrapper

        op_kwargs = settings.model_dump()
        op = weave.op(_fn_wrapper(fn), **op_kwargs)
        return op

    return wrapper


def get_together_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _together_patcher  # noqa: PLW0603
    if _together_patcher is not None:
        return _together_patcher

    base = with_integration_metadata(settings.op_settings, TOGETHER_INTEGRATION)

    create_settings = base.model_copy(
        update={
            "name": base.name or "together.chat.completions.create",
            "kind": base.kind or "llm",
        }
    )

    _together_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("together.resources.chat.completions"),
                "CompletionsResource.create",
                create_wrapper_sync(create_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("together.resources.chat.completions"),
                "AsyncCompletionsResource.create",
                create_wrapper_async(create_settings),
            ),
        ]
    )

    return _together_patcher
