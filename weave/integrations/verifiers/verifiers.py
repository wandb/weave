from __future__ import annotations

import importlib
from functools import wraps
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
    """Return a sync wrapper that converts a function into a Weave op."""
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        return weave.op(fn, **op_kwargs)

    return wrapper


def _verifiers_wrapper_async(settings: OpSettings) -> Callable:
    """Return an async-aware wrapper factory that awaits the original function."""
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        @wraps(fn)
        async def _inner(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        return weave.op(_inner, **op_kwargs)

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
    get_model_response_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.get_model_response"}
    )
    rollout_settings = base.model_copy(
        update={"name": base.name or "verifiers.envs.multiturn_env.MultiTurnEnv.rollout"}
    )
    evaluate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.evaluate"}
    )
    a_generate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.a_generate"}
    )
    generate_settings = base.model_copy(
        update={"name": base.name or "verifiers.Environment.generate"}
    )

    _verifiers_patcher = MultiPatcher(
        [
            # Model calls
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.get_model_response",
                _verifiers_wrapper_async(settings=get_model_response_settings),
            ),
            # Rollouts and batching
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.multiturn_env"),
                "MultiTurnEnv.rollout",
                _verifiers_wrapper_async(settings=rollout_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.evaluate",
                _verifiers_wrapper(evaluate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.a_generate",
                _verifiers_wrapper_async(settings=a_generate_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("verifiers.envs.environment"),
                "Environment.generate",
                _verifiers_wrapper(settings=generate_settings),
            ),
        ]
    )

    return _verifiers_patcher
