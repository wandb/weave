"""Declarative framework for LLM-provider (patching-style) integrations.

Most provider integrations (openai, anthropic, groq, cerebras, mistral, cohere,
...) repeat the same ~80-line skeleton: a module-level singleton patcher, an
``IntegrationSettings`` enabled-gate, one ``OpSettings.model_copy`` per endpoint,
a sync/async ``weave.op`` wrapper, and a ``MultiPatcher`` of hand-written
``SymbolPatcher`` entries. The only genuinely per-provider parts are the list of
endpoints to patch, the streaming accumulator (if any), and whether the async
endpoint needs the ``iscoroutinefunction`` passthrough.

This module captures the repeated structure once. An integration declares its
endpoints with :class:`Endpoint` and exposes a one-line getter backed by
:class:`LLMProviderPatcher`; the framework owns settings defaulting, the
enabled/NoOp gate, singleton caching, per-endpoint ``OpSettings`` derivation, the
sync/async wrapper, and ``MultiPatcher`` assembly.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

import weave
from weave.integrations.integration_utilities import should_use_accumulator
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import _add_accumulator

# (inputs_dict) -> accumulator_fn(acc_state, value) -> new_acc_state
AccumulatorFactory = Callable[[dict], Callable[[Any, Any], Any]]

# Default op "kind" for LLM-provider endpoints, matching the historical
# per-integration ``base.kind or "llm"`` default.
DEFAULT_OP_KIND = "llm"


def make_async_passthrough(fn: Callable) -> Callable:
    """Wrap ``fn`` in a real ``async def`` so ``iscoroutinefunction`` is True.

    Several vendor SDKs (Stainless-generated: openai, anthropic, cerebras, ...)
    expose async client methods that do not themselves pass
    ``inspect.iscoroutinefunction``. ``weave.op`` relies on that check to pick the
    async execution path, so those endpoints must be wrapped. This is opt-in per
    endpoint because some providers' async methods (e.g. groq) already pass the
    check and must NOT be double-wrapped.
    """

    @wraps(fn)
    async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
        return await fn(*args, **kwargs)

    return _async_wrapper


@dataclass(frozen=True)
class Endpoint:
    """Declarative description of one method to patch on a provider SDK."""

    module: str
    """Importable module holding the symbol, e.g. ``"groq.resources.chat.completions"``."""

    symbol: str
    """Dotted attribute on ``module`` to patch, e.g. ``"Completions.create"``."""

    op_name: str
    """Default op name when the integration's settings don't override it."""

    async_passthrough: bool = False
    """Whether to wrap the target in :func:`make_async_passthrough` (see its docs)."""

    accumulator: AccumulatorFactory | None = None
    """Optional streaming-accumulator factory; ``None`` for non-streaming endpoints."""

    should_accumulate: Callable[[dict], bool] | None = None
    """Predicate deciding whether to accumulate for a given call. Defaults to
    :func:`should_use_accumulator` when an accumulator is set."""

    on_finish_post_processor: Callable[[Any], Any] | None = None
    """Optional transform applied to the accumulated output before logging."""


def _build_endpoint_wrapper(
    endpoint: Endpoint, op_settings: OpSettings
) -> Callable[[Callable], Callable]:
    """Return the ``SymbolPatcher`` value factory for one endpoint.

    The returned callable takes the original SDK function and returns the
    ``weave.op``-wrapped replacement (plus an accumulator, if the endpoint
    declares one).
    """
    op_kwargs = op_settings.model_dump()

    def wrapper(fn: Callable) -> Callable:
        target = make_async_passthrough(fn) if endpoint.async_passthrough else fn
        op = weave.op(target, **op_kwargs)
        if endpoint.accumulator is None:
            return op
        return _add_accumulator(
            op,  # type: ignore[arg-type]
            make_accumulator=endpoint.accumulator,
            should_accumulate=endpoint.should_accumulate or should_use_accumulator,
            on_finish_post_processor=endpoint.on_finish_post_processor,
        )

    return wrapper


def derive_endpoint_settings(
    op_settings: OpSettings, endpoint: Endpoint, *, kind: str = DEFAULT_OP_KIND
) -> OpSettings:
    """Derive the per-endpoint ``OpSettings`` from an integration's base settings.

    The endpoint's ``op_name``/``kind`` are used only as fallbacks — explicit
    values on ``op_settings`` win. This is the single home for the name/kind
    resolution rule that each integration used to inline as a ``base.model_copy``
    block (and which historically drifted between integrations).
    """
    return op_settings.model_copy(
        update={
            "name": op_settings.name or endpoint.op_name,
            "kind": op_settings.kind or kind,
        }
    )


def build_llm_provider_patcher(
    op_settings: OpSettings,
    endpoints: list[Endpoint],
    *,
    kind: str = DEFAULT_OP_KIND,
) -> MultiPatcher:
    """Build a :class:`MultiPatcher` from a declarative list of endpoints.

    Each endpoint gets its own ``OpSettings`` via :func:`derive_endpoint_settings`,
    mirroring the per-integration ``base.model_copy`` blocks this replaces. This
    function assumes the integration is enabled; the enabled/NoOp/caching gate
    lives in :class:`LLMProviderPatcher`.
    """
    patchers: list[SymbolPatcher] = []
    for endpoint in endpoints:
        endpoint_settings = derive_endpoint_settings(op_settings, endpoint, kind=kind)
        patchers.append(
            SymbolPatcher(
                # default-arg binds the module string per-iteration (avoids the
                # classic late-binding closure bug where every patcher would
                # import the last endpoint's module).
                lambda module=endpoint.module: importlib.import_module(module),
                endpoint.symbol,
                _build_endpoint_wrapper(endpoint, endpoint_settings),
            )
        )
    return MultiPatcher(patchers)


class LLMProviderPatcher:
    """Holds an integration's endpoints and its singleton patcher.

    Replaces the per-module ``_<name>_patcher`` global plus the boilerplate
    ``get_<name>_patcher`` body. Caching matches the historical behavior exactly:
    a disabled integration returns a fresh :class:`NoOpPatcher` (never cached), and
    the real :class:`MultiPatcher` is built once and reused.
    """

    def __init__(
        self, endpoints: list[Endpoint], *, kind: str = DEFAULT_OP_KIND
    ) -> None:
        self._endpoints = endpoints
        self._kind = kind
        self._patcher: MultiPatcher | None = None

    def get(
        self, settings: IntegrationSettings | None = None
    ) -> MultiPatcher | NoOpPatcher:
        if settings is None:
            settings = IntegrationSettings()
        if not settings.enabled:
            return NoOpPatcher()
        if self._patcher is not None:
            return self._patcher
        self._patcher = build_llm_provider_patcher(
            settings.op_settings, self._endpoints, kind=self._kind
        )
        return self._patcher

    def reset(self) -> None:
        """Drop the cached patcher so the next ``get`` rebuilds it.

        Gives integrations a coordinated reset hook for tests — the per-module
        ``_<name>_patcher`` globals this replaces had no such affordance.
        """
        self._patcher = None
