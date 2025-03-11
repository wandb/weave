from __future__ import annotations

import importlib
from typing import Callable
import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher


_openai_agents_patcher: MultiPatcher | None = None


def openai_agents_wrapper_async(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_openai_agents_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_agents_patcher
    if _openai_agents_patcher is not None:
        return _openai_agents_patcher

    base = settings.op_settings

    # Naming convention -- module_method_settings
    runner_run_settings = base.model_copy(
        update={
            "name": base.name or "agents.Runner.run",
            "call_display_name": base.call_display_name,
            # "postprocess_inputs": ,
        }
    )

    patchers = [
        SymbolPatcher(
            lambda: importlib.import_module("agents"),
            "Runner.run",
            openai_agents_wrapper_async(runner_run_settings),
        ),
    ]

    _openai_agents_patcher = MultiPatcher(patchers)

    return _openai_agents_patcher
