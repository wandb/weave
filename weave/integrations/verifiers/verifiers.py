from __future__ import annotations

import importlib
from typing import Any, Callable, Optional

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_verifiers_patcher: Optional[MultiPatcher] = None


def _verifiers_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    if "self" in inputs:
        cls = inputs["self"].__class__
        inputs["self"] = {
            "__class__": {
                "module": cls.__module__,
                "qualname": getattr(cls, "__qualname__", cls.__name__),
                "name": cls.__name__,
            }
        }
    return inputs


def _verifiers_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        return weave.op(fn, **op_kwargs)

    return wrapper


def get_verifiers_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _verifiers_patcher
    if _verifiers_patcher is not None:
        return _verifiers_patcher

    base: OpSettings = settings.op_settings
    evaluate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.evaluate"}
    )

    _verifiers_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.evaluate",
                _verifiers_wrapper(evaluate_settings),
            ),
        ]
    )

    return _verifiers_patcher
