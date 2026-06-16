"""Tests for op-level default attributes and formalized integration metadata.

The mechanism: `op(attributes=...)` (and `OpSettings.attributes`) stamps default
attributes onto every call an op creates, at the lowest precedence. Integrations
use `IntegrationMetadata` to render an `attributes["integration"]` provenance
block and `with_integration_metadata` to thread it through `OpSettings`.
"""

from __future__ import annotations

import pytest

import weave
from weave.integrations.integration_metadata import (
    INTEGRATION_ATTRIBUTE_KEY,
    IntegrationMetadata,
    apply_integration_metadata,
    library_integration,
    resolve_package_version,
    with_integration_metadata,
)
from weave.trace.autopatch import OpSettings
from weave.version import VERSION as WEAVE_VERSION


def _only_call(client):
    calls = list(client.get_calls())
    assert len(calls) == 1
    return calls[0]


# --- IntegrationMetadata model -------------------------------------------------


def test_as_attributes_shape():
    meta = IntegrationMetadata(name="openai", version="1.2.3", meta={"k": "v"})
    assert meta.as_attributes() == {
        "integration": {"name": "openai", "version": "1.2.3", "meta": {"k": "v"}}
    }


def test_version_defaults_to_weave_sdk_version():
    assert IntegrationMetadata(name="openai").version == WEAVE_VERSION


def test_as_otel_attributes_flattens_to_dotted_keys():
    meta = IntegrationMetadata(
        name="openai_agents",
        version="1.2.3",
        meta={"package_name": "openai-agents", "package_version": "0.1.0"},
    )
    assert meta.as_otel_attributes() == {
        "integration.name": "openai_agents",
        "integration.version": "1.2.3",
        "integration.meta.package_name": "openai-agents",
        "integration.meta.package_version": "0.1.0",
    }


def test_as_otel_attributes_stringifies_non_scalar_meta():
    meta = IntegrationMetadata(name="demo", version="1", meta={"opts": {"a": 1}})
    otel = meta.as_otel_attributes()
    # Nested values are not OTel-legal scalars, so they are stringified.
    assert otel["integration.meta.opts"] == "{'a': 1}"


def test_as_attributes_returns_fresh_copies():
    meta = IntegrationMetadata(name="openai", meta={"k": "v"})
    first = meta.as_attributes()
    first["integration"]["meta"]["k"] = "mutated"
    # Mutating the returned dict must not leak back into the instance.
    assert meta.as_attributes()["integration"]["meta"] == {"k": "v"}


def test_library_integration_records_package_version():
    # `weave` is always installed in the test environment. Note the resolved
    # package version is PEP 440-normalized (e.g. "0.52.43.dev0"), which may
    # differ in punctuation from the declared VERSION ("0.52.43-dev0").
    meta = library_integration("weave-self-test", distribution_name="weave")
    assert meta.name == "weave-self-test"
    assert meta.version == WEAVE_VERSION
    assert meta.meta["package_name"] == "weave"
    assert isinstance(meta.meta["package_version"], str)
    assert meta.meta["package_version"]


def test_library_integration_missing_package_omits_version():
    meta = library_integration(
        "ghost", distribution_name="definitely-not-installed-xyz"
    )
    assert meta.meta == {"package_name": "definitely-not-installed-xyz"}


def test_library_integration_extra_meta():
    meta = library_integration(
        "weave-self-test", distribution_name="weave", flavor="async"
    )
    assert meta.meta["flavor"] == "async"


def test_resolve_package_version_unknown_returns_none():
    assert resolve_package_version("definitely-not-installed-xyz") is None


def test_with_integration_metadata_is_nonmutating_and_preserved_through_copy():
    base = OpSettings(name="base")
    out = with_integration_metadata(base, IntegrationMetadata(name="openai"))

    # Original settings untouched.
    assert base.attributes is None
    # Returned settings carry the integration block.
    assert out.attributes[INTEGRATION_ATTRIBUTE_KEY]["name"] == "openai"

    # Derived settings (the real-world pattern) keep the integration block.
    derived = out.model_copy(update={"name": "derived", "kind": "llm"})
    assert derived.attributes[INTEGRATION_ATTRIBUTE_KEY]["name"] == "openai"


def test_with_integration_metadata_preserves_existing_attributes():
    base = OpSettings(name="base", attributes={"team": "search"})
    out = with_integration_metadata(base, IntegrationMetadata(name="openai"))
    assert out.attributes["team"] == "search"
    assert out.attributes[INTEGRATION_ATTRIBUTE_KEY]["name"] == "openai"


# --- op-level default attributes (end to end) ---------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("flavor", ["sync", "async", "sync_gen", "async_gen"])
async def test_op_level_attributes_land_on_call(client, flavor):
    """op(attributes=...) stamps the integration block on every call flavor."""
    if flavor == "sync":

        @weave.op(attributes={"integration": {"name": "demo"}})
        def func():
            return 1

        func()
    elif flavor == "async":

        @weave.op(attributes={"integration": {"name": "demo"}})
        async def func():
            return 1

        await func()
    elif flavor == "sync_gen":

        @weave.op(attributes={"integration": {"name": "demo"}})
        def func():
            yield 1
            yield 2

        list(func())
    elif flavor == "async_gen":

        @weave.op(attributes={"integration": {"name": "demo"}})
        async def func():
            yield 1
            yield 2

        [x async for x in func()]
    else:
        raise AssertionError(f"unhandled flavor {flavor}")

    call = _only_call(client)
    assert call.attributes["integration"] == {"name": "demo"}


def test_op_level_attributes_coexist_with_context(client):
    @weave.op(attributes={"integration": {"name": "demo"}})
    def func():
        return 1

    with weave.attributes({"env": "prod"}):
        func()

    call = _only_call(client)
    assert call.attributes["integration"] == {"name": "demo"}
    assert call.attributes["env"] == "prod"


def test_context_attributes_override_op_level_on_collision(client):
    @weave.op(attributes={"integration": {"name": "demo"}})
    def func():
        return 1

    with weave.attributes({"integration": "user-override"}):
        func()

    # Op-level defaults are the lowest precedence: the user context wins.
    call = _only_call(client)
    assert call.attributes["integration"] == "user-override"


def test_op_level_attributes_do_not_clobber_weave_subdict(client):
    @weave.op(kind="llm", attributes={"integration": {"name": "demo"}})
    def func():
        return 1

    func()
    call = _only_call(client)
    assert call.attributes["integration"] == {"name": "demo"}
    # The reserved weave subdict (kind) must survive alongside op attributes.
    assert call.attributes["weave"]["kind"] == "llm"


def test_op_rejects_reserved_weave_key():
    with pytest.raises(ValueError, match="reserved 'weave' key"):

        @weave.op(attributes={"weave": {"kind": "llm"}})
        def func():
            return 1


def test_op_without_attributes_has_no_integration_key(client):
    @weave.op
    def func():
        return 1

    func()
    call = _only_call(client)
    assert "integration" not in call.attributes


# --- callback/tracer path (Family B: direct create_call) ----------------------


def test_create_call_carries_integration_attributes(client):
    """Integrations that build attributes directly still land integration data."""
    attrs = {"trace_id": "t1"}
    apply_integration_metadata(
        attrs, library_integration("demo", distribution_name="weave")
    )

    call = client.create_call("demo.op", inputs={}, attributes=attrs)
    client.finish_call(call)

    fetched = _only_call(client)
    assert fetched.attributes["integration"]["name"] == "demo"
    assert fetched.attributes["integration"]["meta"]["package_name"] == "weave"
    assert fetched.attributes["trace_id"] == "t1"


def test_apply_integration_metadata_preserves_existing_integration():
    attrs = {"integration": "user-set"}
    apply_integration_metadata(attrs, IntegrationMetadata(name="demo"))
    # setdefault semantics: an existing integration value is not overwritten.
    assert attrs["integration"] == "user-set"
