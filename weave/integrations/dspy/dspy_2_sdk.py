from __future__ import annotations

import importlib
from typing import Any, Callable

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.serialize import dictify

_dspy_patcher: MultiPatcher | None = None


def dspy_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        inputs["self"] = dictify(inputs["self"])
        if inputs["self"]["__class__"]["module"] == "__main__":
            inputs["self"]["__class__"]["module"] = ""
    return inputs


def dspy_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = dspy_postprocess_inputs
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def get_dspy_2_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _dspy_patcher
    if _dspy_patcher is not None:
        return _dspy_patcher

    base = settings.op_settings

    dspy_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("dspy.clients.lm"),
                "LM.__call__",
                dspy_wrapper(base.model_copy(update={"name": base.name or "dspy.LM"})),
            ),
        ]
    )

    return dspy_patcher
