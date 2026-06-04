"""Unit tests for the declarative LLM-provider integration framework.

These exercise ``weave.integrations._llm_provider`` directly — no vendor SDK, no
VCR cassette, and no live weave client. That is the point: the structural logic
every provider integration used to inline (enabled/NoOp gate, singleton caching,
per-endpoint op-name derivation, the async passthrough) is now verifiable in
isolation, which was not possible when it lived as copy-pasted boilerplate behind
each provider's recorded HTTP tests.
"""

from __future__ import annotations

import inspect

from weave.integrations._llm_provider import (
    Endpoint,
    LLMProviderPatcher,
    _build_endpoint_wrapper,
    derive_endpoint_settings,
    make_async_passthrough,
)
from weave.integrations.patcher import MultiPatcher, NoOpPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings


def _endpoint(**overrides: object) -> Endpoint:
    kwargs: dict[str, object] = {
        "module": "some.sdk.module",
        "symbol": "SomeResource.create",
        "op_name": "provider.chat.completions.create",
    }
    kwargs.update(overrides)
    return Endpoint(**kwargs)  # type: ignore[arg-type]


def test_make_async_passthrough_is_coroutine_function() -> None:
    def sync_fn() -> None: ...

    assert not inspect.iscoroutinefunction(sync_fn)
    assert inspect.iscoroutinefunction(make_async_passthrough(sync_fn))


def test_disabled_settings_returns_noop_patcher() -> None:
    provider = LLMProviderPatcher([_endpoint()])
    assert isinstance(provider.get(IntegrationSettings(enabled=False)), NoOpPatcher)


def test_enabled_returns_multipatcher_caches_and_resets() -> None:
    provider = LLMProviderPatcher(
        [_endpoint(), _endpoint(symbol="SomeResource.acreate")]
    )

    first = provider.get(IntegrationSettings())
    assert isinstance(first, MultiPatcher)
    assert len(first.patchers) == 2  # one SymbolPatcher per endpoint

    # The real patcher is built once and reused.
    assert provider.get(IntegrationSettings()) is first

    # reset() gives a coordinated way to rebuild (the old module-global
    # singletons had no such hook).
    provider.reset()
    assert provider.get(IntegrationSettings()) is not first


def test_endpoint_op_name_is_used_when_settings_do_not_override() -> None:
    derived = derive_endpoint_settings(
        OpSettings(), _endpoint(op_name="myprovider.chat.create")
    )
    assert derived.name == "myprovider.chat.create"
    assert derived.kind == "llm"  # default kind applied


def test_explicit_settings_name_overrides_endpoint_op_name() -> None:
    derived = derive_endpoint_settings(
        OpSettings(name="custom.op.name", kind="tool"),
        _endpoint(op_name="myprovider.chat.create"),
    )
    # Explicit base settings win over the endpoint's fallbacks.
    assert derived.name == "custom.op.name"
    assert derived.kind == "tool"


def test_endpoint_wrapper_uses_resolved_settings_name() -> None:
    # The wrapper consumes already-resolved settings; it should produce an op
    # carrying that resolved name.
    wrapper = _build_endpoint_wrapper(_endpoint(), OpSettings(name="resolved.name"))

    def some_sdk_method(a: int, b: int) -> int:
        return a + b

    op = wrapper(some_sdk_method)
    assert op.name == "resolved.name"


def test_async_passthrough_endpoint_produces_coroutine_op() -> None:
    wrapper = _build_endpoint_wrapper(_endpoint(async_passthrough=True), OpSettings())

    def sync_sdk_method() -> None: ...

    op = wrapper(sync_sdk_method)
    # The op must look async so weave.op routes it through the async path.
    assert inspect.iscoroutinefunction(op.resolve_fn)


def test_non_passthrough_endpoint_preserves_sync_function() -> None:
    wrapper = _build_endpoint_wrapper(_endpoint(), OpSettings())

    def sync_sdk_method() -> None: ...

    op = wrapper(sync_sdk_method)
    assert not inspect.iscoroutinefunction(op.resolve_fn)
