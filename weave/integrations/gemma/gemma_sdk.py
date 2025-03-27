"""
This module provides integrations between Weave and Gemma, allowing Weave to trace
Gemma multi-turn, multi-modal conversations. For more details on Gemma, visit:
https://gemma-llm.readthedocs.io/en/latest/index.html
"""

import importlib
from typing import Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.serialization.serialize import dictify


_gemma_patcher: MultiPatcher | None = None


def gemma_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_gemma_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _gemma_patcher
    if _gemma_patcher is not None:
        return _gemma_patcher

    base = settings.op_settings

    