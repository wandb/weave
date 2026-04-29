from __future__ import annotations

import functools
import importlib
import inspect
from collections.abc import Callable
from typing import Any

import weave
from weave.integrations.gepa.gepa_callback import WeaveGEPACallback
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_gepa_patcher: MultiPatcher | None = None


def _fn_accepts_callbacks(fn: Callable) -> bool:
    """Return True if `fn` accepts a `callbacks` keyword argument.

    Used once at patch time as a safety net: gepa < 0.1 (which dspy 3.1.x
    pins) doesn't have the callback protocol yet, so injecting `callbacks=`
    against those versions would break `dspy.GEPA.compile()`.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    params = sig.parameters
    if "callbacks" in params:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _add_weave_callback(kwargs: dict[str, Any]) -> None:
    """Add a WeaveGEPACallback to the `callbacks` kwarg if one is not present."""
    existing = kwargs.get("callbacks")
    if existing is None:
        kwargs["callbacks"] = [WeaveGEPACallback()]
        return
    for cb in existing:
        if isinstance(cb, WeaveGEPACallback):
            return
    kwargs["callbacks"] = [*existing, WeaveGEPACallback()]


def _optimize_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Drop heavy/unserializable fields from the top-level optimize span."""
    safe = dict(inputs)
    for key in ("adapter", "evaluator", "reflection_lm", "task_lm", "logger"):
        if key in safe and not isinstance(
            safe[key], (str, int, float, bool, type(None))
        ):
            safe[key] = repr(safe[key])
    if "callbacks" in safe:
        safe["callbacks"] = [repr(cb) for cb in (safe["callbacks"] or [])]
    return safe


def _optimize_postprocess_output(output: Any) -> Any:
    """Summarize a GEPAResult for compact logging."""
    if output is None:
        return None
    summary: dict[str, Any] = {"__class__": type(output).__name__}
    for attr in (
        "best_candidate",
        "best_idx",
        "num_candidates",
        "num_metric_calls",
        "val_aggregate_scores",
    ):
        if hasattr(output, attr):
            value = getattr(output, attr)
            try:
                summary[attr] = (
                    value
                    if isinstance(
                        value, (dict, list, str, int, float, bool, type(None))
                    )
                    else repr(value)
                )
            except Exception:
                summary[attr] = repr(value)
    return summary


def _wrap_optimize(
    settings: OpSettings,
    *,
    inject_callback: bool,
) -> Callable[[Callable], Callable]:
    """Wrap a top-level GEPA entrypoint as a Weave op.

    Args:
        inject_callback: Whether this entrypoint accepts a `callbacks=` kwarg
            we should inject our `WeaveGEPACallback` into. True for the
            `gepa.optimize` family (gepa>=0.1); False for
            `gepa.optimize_anything` which has a different config and never
            accepted `callbacks`. We additionally re-check `fn`'s signature
            once at patch time so a stale gepa<0.1 (e.g. pulled in by dspy
            3.1.x) silently degrades to span-only tracing instead of
            TypeError-ing on injection.
    """

    def wrapper(fn: Callable) -> Callable:
        actually_inject = inject_callback and _fn_accepts_callbacks(fn)

        @functools.wraps(fn)
        def _inner(*args: Any, **kwargs: Any) -> Any:
            if actually_inject:
                _add_weave_callback(kwargs)
            return fn(*args, **kwargs)

        op_kwargs = settings.model_dump()
        if not op_kwargs.get("postprocess_inputs"):
            op_kwargs["postprocess_inputs"] = _optimize_postprocess_inputs
        if not op_kwargs.get("postprocess_output"):
            op_kwargs["postprocess_output"] = _optimize_postprocess_output
        return weave.op(_inner, **op_kwargs)

    return wrapper


def get_gepa_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _gepa_patcher  # noqa: PLW0603
    if _gepa_patcher is not None:
        return _gepa_patcher

    base = settings.op_settings
    optimize_settings = base.model_copy(update={"name": base.name or "gepa.optimize"})
    optimize_anything_settings = base.model_copy(
        update={"name": base.name or "gepa.optimize_anything"}
    )

    _gepa_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("gepa.api"),
                "optimize",
                _wrap_optimize(optimize_settings, inject_callback=True),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("gepa"),
                "optimize",
                _wrap_optimize(optimize_settings, inject_callback=True),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("gepa.optimize_anything"),
                "optimize_anything",
                # `optimize_anything` uses a `GEPAConfig` object, not a
                # `callbacks=` kwarg, so we just trace the call as an op.
                _wrap_optimize(optimize_anything_settings, inject_callback=False),
            ),
        ]
    )

    return _gepa_patcher
