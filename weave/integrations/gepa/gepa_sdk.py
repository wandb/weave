from __future__ import annotations

import functools
import importlib
from collections.abc import Callable
from typing import Any

import weave
from weave.integrations.gepa.gepa_callback import WeaveGEPACallback
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_gepa_patcher: MultiPatcher | None = None


def _inject_weave_callback(kwargs: dict[str, Any]) -> None:
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
        if key in safe and not isinstance(safe[key], (str, int, float, bool, type(None))):
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
                summary[attr] = value if isinstance(value, (dict, list, str, int, float, bool, type(None))) else repr(value)
            except Exception:
                summary[attr] = repr(value)
    return summary


def _wrap_optimize(settings: OpSettings) -> Callable[[Callable], Callable]:
    """Wrap `gepa.optimize` so it injects a Weave callback and traces as an op."""

    def wrapper(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def _inner(*args: Any, **kwargs: Any) -> Any:
            _inject_weave_callback(kwargs)
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
                _wrap_optimize(optimize_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("gepa"),
                "optimize",
                _wrap_optimize(optimize_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("gepa.optimize_anything"),
                "optimize_anything",
                _wrap_optimize(optimize_anything_settings),
            ),
        ]
    )

    return _gepa_patcher
