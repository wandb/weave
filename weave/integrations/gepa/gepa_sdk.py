from __future__ import annotations

import importlib
from collections.abc import Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_gepa_patcher: MultiPatcher | None = None


def _gepa_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        return weave.op(fn, **settings.model_dump())

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
                lambda: importlib.import_module("gepa"),
                "optimize",
                _gepa_wrapper(optimize_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("gepa.api"),
                "optimize",
                _gepa_wrapper(optimize_settings),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("gepa.optimize_anything"),
                "optimize_anything",
                _gepa_wrapper(optimize_anything_settings),
            ),
        ]
    )

    return _gepa_patcher
