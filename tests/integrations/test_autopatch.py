"""Tests for the automatic patching mechanism."""

from __future__ import annotations

import sys
import types
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

import weave.integrations.patch as patch_module
from weave.integrations.patch import (
    _PATCHED_INTEGRATIONS,
    _patch_if_needed,
    _patch_integration,
    implicit_patch,
    patch_openai,
    patch_openai_agents,
    register_import_hook,
    reset_patched_integrations,
    unregister_import_hook,
)
from weave.trace import weave_init


def _reset_import(monkeypatch, module: str):
    if module in sys.modules:
        monkeypatch.delitem(sys.modules, module, raising=False)


def _inject_fake_module(monkeypatch, module_name: str):
    m = cast(Any, types.ModuleType(module_name))
    monkeypatch.setitem(sys.modules, module_name, m)
    return m


@pytest.fixture
def setup_env(monkeypatch):
    reset_patched_integrations()
    unregister_import_hook()

    monkeypatch.delenv("WEAVE_IMPLICITLY_PATCH_INTEGRATIONS", raising=False)
    monkeypatch.delenv("WEAVE_DISABLED", raising=False)

    for module in ["openai", "anthropic", "mistralai", "groq", "litellm"]:
        _reset_import(monkeypatch, module)

    yield
    reset_patched_integrations()
    unregister_import_hook()


def test_implicit_patch_already_imported(setup_env, monkeypatch):
    """Test that implicit_patch patches libraries that are already imported."""
    _inject_fake_module(monkeypatch, "openai")

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        implicit_patch()
        mock_patch_func.assert_called_once()


def test_implicit_patch_multiple_libraries(setup_env, monkeypatch):
    """Test that implicit_patch patches multiple already-imported libraries."""
    _inject_fake_module(monkeypatch, "openai")
    _inject_fake_module(monkeypatch, "anthropic")
    _inject_fake_module(monkeypatch, "mistralai")

    mock_patch_openai = MagicMock()
    mock_patch_anthropic = MagicMock()
    mock_patch_mistral = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {
            "openai": mock_patch_openai,
            "anthropic": mock_patch_anthropic,
            "mistralai": mock_patch_mistral,
        },
    ):
        implicit_patch()

        mock_patch_openai.assert_called_once()
        mock_patch_anthropic.assert_called_once()
        mock_patch_mistral.assert_called_once()


# The real modules realtime wraps. Tests below isolate the one under test by
# clearing all three from sys.modules first, then injecting only the target.
# Otherwise, since aiohttp/websockets are genuinely installed here, an un-mocked
# sibling key still in sys.modules would let the real patch_openai_realtime fire
# and pre-populate _PATCHED_INTEGRATIONS.
_REALTIME_TRIGGER_MODULES = ["websocket", "websockets", "aiohttp"]


def test_implicit_patch_realtime_websocket_already_imported(setup_env, monkeypatch):
    """Realtime auto-patches when its real trigger module (websocket) is imported.

    Mirrors ``test_implicit_patch_already_imported`` but keys on ``websocket``,
    one of the real modules the realtime patcher wraps (the old synthetic
    ``openai_realtime`` key never matched ``sys.modules`` so it never fired).
    """
    for module in _REALTIME_TRIGGER_MODULES:
        _reset_import(monkeypatch, module)
    _inject_fake_module(monkeypatch, "websocket")

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"websocket": mock_patch_func},
    ):
        implicit_patch()
        mock_patch_func.assert_called_once()


@pytest.mark.parametrize("module_name", _REALTIME_TRIGGER_MODULES)
def test_implicit_patch_realtime_trigger_modules(setup_env, monkeypatch, module_name):
    """Each of the three real modules realtime wraps triggers its patch func."""
    for module in _REALTIME_TRIGGER_MODULES:
        _reset_import(monkeypatch, module)
    _inject_fake_module(monkeypatch, module_name)

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {module_name: mock_patch_func},
    ):
        implicit_patch()
        mock_patch_func.assert_called_once()


def test_realtime_registered_under_real_trigger_modules(setup_env):
    """The real mapping wires realtime to the modules it instruments, not a
    synthetic ``openai_realtime`` key that never matched ``sys.modules``.
    """
    mapping = patch_module.INTEGRATION_MODULE_MAPPING
    for module_name in ("websocket", "websockets", "aiohttp"):
        assert mapping[module_name] is patch_module.patch_openai_realtime
    assert "openai_realtime" not in mapping


def test_implicit_patch_disabled(setup_env, monkeypatch):
    """Test that implicit patching can be disabled via environment variable."""
    monkeypatch.setenv("WEAVE_IMPLICITLY_PATCH_INTEGRATIONS", "false")
    _inject_fake_module(monkeypatch, "openai")

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        implicit_patch()
        mock_patch_func.assert_not_called()


def test_import_hook_patches_on_import(setup_env, monkeypatch):
    """Test that the import hook patches libraries when they are imported after weave.init()."""
    register_import_hook()

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        _inject_fake_module(monkeypatch, "openai")
        from weave.integrations.patch import _patch_if_needed

        _patch_if_needed("openai")
        mock_patch_func.assert_called_once()


def test_import_hook_disabled(setup_env, monkeypatch):
    """Test that import hook is not registered when implicit patching is disabled."""
    monkeypatch.setenv("WEAVE_IMPLICITLY_PATCH_INTEGRATIONS", "false")

    register_import_hook()
    assert patch_module._IMPORT_HOOK is None


def test_no_double_patching(setup_env, monkeypatch):
    """Test that libraries are not patched multiple times."""
    _inject_fake_module(monkeypatch, "openai")

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        implicit_patch()
        assert mock_patch_func.call_count == 1

        _PATCHED_INTEGRATIONS.add("openai")

        implicit_patch()
        assert mock_patch_func.call_count == 1


def test_patch_failure_graceful(setup_env, monkeypatch):
    """Test that patching failures are handled gracefully."""
    _inject_fake_module(monkeypatch, "openai")

    mock_patch_func = MagicMock(side_effect=Exception("Patch failed"))

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        implicit_patch()
        mock_patch_func.assert_called_once()


def test_init_weave_calls_patching(setup_env, monkeypatch):
    """Test that init_weave calls implicit_patch and register_import_hook."""
    patch_calls = {"implicit_patch": 0, "register_import_hook": 0}

    def mock_implicit_patch():
        patch_calls["implicit_patch"] += 1

    def mock_register_import_hook():
        patch_calls["register_import_hook"] += 1

    with (
        patch("weave.integrations.patch.implicit_patch", mock_implicit_patch),
        patch(
            "weave.integrations.patch.register_import_hook", mock_register_import_hook
        ),
        patch.object(weave_init, "init_weave_get_server") as mock_get_server,
        patch(
            "weave.wandb_interface.context.get_wandb_api_context"
        ) as mock_get_context,
        patch.object(weave_init, "get_username") as mock_get_username,
        patch("weave.trace.init_message.print_init_message") as mock_print_message,
    ):
        mock_get_context.return_value = MagicMock(api_key="test_key")
        mock_server = MagicMock()
        mock_server.server_info.return_value.min_required_weave_python_version = "0.0.0"
        mock_get_server.return_value = mock_server
        mock_get_username.return_value = "test_user"

        client = weave_init.init_weave("test_entity/test_project")

        assert patch_calls["implicit_patch"] == 1
        assert patch_calls["register_import_hook"] == 1

        if client:
            try:
                client.finish()
            except Exception:
                pass


def test_implicit_patching_disabled_via_settings(setup_env, monkeypatch):
    """Test that implicit patching can be disabled via settings."""
    _inject_fake_module(monkeypatch, "openai")

    mock_patch_func = MagicMock()

    with (
        patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"openai": mock_patch_func},
        ),
        patch(
            "weave.trace.settings.should_implicitly_patch_integrations"
        ) as mock_should_patch,
    ):
        mock_should_patch.return_value = False

        implicit_patch()
        mock_patch_func.assert_not_called()

        register_import_hook()
        assert patch_module._IMPORT_HOOK is None


def test_patch_if_needed(setup_env, monkeypatch):
    """Test the _patch_if_needed helper function."""
    _inject_fake_module(monkeypatch, "openai")

    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        _patch_if_needed("openai")
        mock_patch_func.assert_called_once()

        _PATCHED_INTEGRATIONS.add("openai")

        mock_patch_func.reset_mock()
        _patch_if_needed("openai")
        mock_patch_func.assert_not_called()


def test_explicit_patch_still_works(setup_env, monkeypatch):
    """Test that explicit patching still works alongside implicit patching."""
    _inject_fake_module(monkeypatch, "openai")

    mock_patcher = MagicMock()
    mock_patcher.attempt_patch.return_value = True
    mock_get_patcher = MagicMock(return_value=mock_patcher)

    fake_module = types.ModuleType("weave.integrations.openai.openai_sdk")
    fake_module.get_openai_patcher = mock_get_patcher

    with patch(
        "weave.integrations.patch.importlib.import_module",
        return_value=fake_module,
    ):
        patch_openai()

        mock_get_patcher.assert_called_once()
        mock_patcher.attempt_patch.assert_called_once()

        assert "openai" in patch_module._PATCHED_INTEGRATIONS


def test_reset_patched_integrations(setup_env, monkeypatch):
    """Test that reset_patched_integrations clears the patched set."""
    patch_module._PATCHED_INTEGRATIONS.add("openai")
    patch_module._PATCHED_INTEGRATIONS.add("anthropic")
    assert len(patch_module._PATCHED_INTEGRATIONS) == 2

    reset_patched_integrations()
    assert len(patch_module._PATCHED_INTEGRATIONS) == 0


def test_unregister_import_hook(setup_env):
    """Test that unregister_import_hook removes the hook from sys.meta_path."""
    register_import_hook()
    assert patch_module._IMPORT_HOOK is not None
    assert patch_module._IMPORT_HOOK in sys.meta_path

    unregister_import_hook()
    assert patch_module._IMPORT_HOOK is None


@pytest.mark.parametrize("success", [True, False])
def test_patch_integration(setup_env, success):
    """The basic case where a single integration is patched and it has a single
    triggering symbol.

    SUCCESS:
        1. Patcher is called once;
        2. Symbol is tracked in patched_integrations.
        3. Subsequent calls to _patch_integration for the same integration do not trigger a new patch.
    """
    mock_patcher = MagicMock()
    mock_patcher.attempt_patch.return_value = success
    mock_getter = MagicMock(return_value=mock_patcher)

    fake_module = types.ModuleType("fake_integration_module")
    fake_module.get_fake_patcher = mock_getter

    with patch(
        "weave.integrations.patch.importlib.import_module",
        return_value=fake_module,
    ):
        # First call - should patch
        _patch_integration(
            module_path="fake.integration.module",
            patcher_func_getter_name="get_fake_patcher",
            triggering_symbols=["single_symbol"],
        )

        mock_getter.assert_called_once()
        mock_patcher.attempt_patch.assert_called_once()

        # True if patched, False if not
        assert ("single_symbol" in patch_module._PATCHED_INTEGRATIONS) is success

        # Second call behavior depends on whether first patch succeeded
        mock_getter.reset_mock()
        mock_patcher.reset_mock()
        _patch_integration(
            module_path="fake.integration.module",
            patcher_func_getter_name="get_fake_patcher",
            triggering_symbols=["single_symbol"],
        )

        if success:
            # If first patch succeeded, should NOT patch again
            mock_getter.assert_not_called()
            mock_patcher.attempt_patch.assert_not_called()
        else:
            # If first patch failed, should try again (symbol wasn't added to _PATCHED_INTEGRATIONS)
            mock_getter.assert_called_once()
            mock_patcher.attempt_patch.assert_called_once()
        assert ("single_symbol" in patch_module._PATCHED_INTEGRATIONS) is success


def test_direct_openai_patched_by_default_without_agents(setup_env, monkeypatch):
    """Direct openai use is implicitly patched under the default settings
    (``use_otel_v2=True``) when the Agents SDK is not imported.

    Pins the WB-37240 regression where ``_dispatch_openai`` skipped openai
    entirely in OTel V2 mode, silently dropping spans/usage for direct calls.
    """
    assert patch_module.INTEGRATION_MODULE_MAPPING["openai"] is patch_openai
    _reset_import(monkeypatch, "agents")
    _inject_fake_module(monkeypatch, "openai")

    openai_patcher = MagicMock()
    openai_patcher.attempt_patch.return_value = True
    fake_openai_sdk = cast(
        Any, types.ModuleType("weave.integrations.openai.openai_sdk")
    )
    fake_openai_sdk.get_openai_patcher = MagicMock(return_value=openai_patcher)

    def fake_import(path: str) -> types.ModuleType:
        if path == "weave.integrations.openai.openai_sdk":
            return fake_openai_sdk
        raise ImportError(path)

    with patch(
        "weave.integrations.patch.importlib.import_module", side_effect=fake_import
    ):
        implicit_patch()

    openai_patcher.attempt_patch.assert_called_once()
    assert "openai" in patch_module._PATCHED_INTEGRATIONS
    assert "openai" not in patch_module._SUPPRESSED_INTEGRATIONS


def test_openai_agents_otel_suppresses_direct_openai(setup_env, monkeypatch):
    """When the OTel agents processor patches, direct openai patching is
    suppressed on every path (implicit, explicit, import hook) so in-agent
    LLM calls are not double-logged.
    """
    # Agents must precede openai in the mapping so the suppression lands
    # before implicit_patch reaches openai.
    keys = list(patch_module.INTEGRATION_MODULE_MAPPING)
    assert keys.index("agents") < keys.index("openai")

    _inject_fake_module(monkeypatch, "agents")
    _inject_fake_module(monkeypatch, "openai")

    agents_patcher = MagicMock()
    agents_patcher.attempt_patch.return_value = True
    fake_agents_mod = cast(
        Any, types.ModuleType("weave.integrations.openai_agents.patcher")
    )
    fake_agents_mod.get_openai_agents_otel_patcher = MagicMock(
        return_value=agents_patcher
    )

    openai_factory = MagicMock()
    fake_openai_sdk = cast(
        Any, types.ModuleType("weave.integrations.openai.openai_sdk")
    )
    fake_openai_sdk.get_openai_patcher = openai_factory

    def fake_import(path: str) -> types.ModuleType:
        if path == "weave.integrations.openai_agents.patcher":
            return fake_agents_mod
        if path == "weave.integrations.openai.openai_sdk":
            return fake_openai_sdk
        raise ImportError(path)

    with patch(
        "weave.integrations.patch.importlib.import_module", side_effect=fake_import
    ):
        implicit_patch()
        agents_patcher.attempt_patch.assert_called_once()
        assert "openai_agents_otel" in patch_module._PATCHED_INTEGRATIONS
        assert "openai" in patch_module._SUPPRESSED_INTEGRATIONS
        assert "openai" not in patch_module._PATCHED_INTEGRATIONS

        patch_openai()
        _patch_if_needed("openai")
        openai_factory.assert_not_called()


def test_legacy_openai_agents_patch_does_not_suppress_openai(setup_env):
    """The calls-based agents patcher (non-OTel path) leaves direct openai
    patching enabled, preserving pre-OTel-V2 behavior.
    """
    agents_patcher = MagicMock()
    agents_patcher.attempt_patch.return_value = True
    fake_agents_mod = cast(
        Any, types.ModuleType("weave.integrations.openai_agents.patcher")
    )
    fake_agents_mod.get_openai_agents_patcher = MagicMock(return_value=agents_patcher)

    with patch(
        "weave.integrations.patch.importlib.import_module",
        return_value=fake_agents_mod,
    ):
        patch_openai_agents()

    assert "openai_agents" in patch_module._PATCHED_INTEGRATIONS
    assert "openai" not in patch_module._SUPPRESSED_INTEGRATIONS


@pytest.mark.parametrize("success", [True, False])
def test_patch_integration_multi(setup_env, success):
    """A secondary case where a single integration is patched and it has
    multiple triggering symbols.  This is common for libraries like langchain
    or crewai where users may not necessarily just import the root module, but
    rather some combination of submodules.

    SUCCESS:
        1. Patcher is called once;
        2. All symbols for this integration are tracked in patched_integrations.
        3. Subsequent calls to _patch_integration for the same integration do not trigger a new patch.
    """
    mock_patcher = MagicMock()
    mock_patcher.attempt_patch.return_value = success
    mock_getter = MagicMock(return_value=mock_patcher)

    fake_module = types.ModuleType("fake_integration_module")
    fake_module.get_fake_patcher = mock_getter

    with patch(
        "weave.integrations.patch.importlib.import_module",
        return_value=fake_module,
    ):
        # First call - should patch
        _patch_integration(
            module_path="fake.integration.module",
            patcher_func_getter_name="get_fake_patcher",
            triggering_symbols=["symbol1", "symbol2", "symbol3"],
        )

        mock_getter.assert_called_once()
        mock_patcher.attempt_patch.assert_called_once()

        # All True if patched, all False if not
        assert ("symbol1" in patch_module._PATCHED_INTEGRATIONS) is success
        assert ("symbol2" in patch_module._PATCHED_INTEGRATIONS) is success
        assert ("symbol3" in patch_module._PATCHED_INTEGRATIONS) is success

        # Second call behavior depends on whether first patch succeeded
        mock_getter.reset_mock()
        mock_patcher.reset_mock()
        _patch_integration(
            module_path="fake.integration.module",
            patcher_func_getter_name="get_fake_patcher",
            triggering_symbols=["symbol1", "symbol2", "symbol3"],
        )

        if success:
            # If first patch succeeded, should NOT patch again (checking by any of the symbols)
            mock_getter.assert_not_called()
            mock_patcher.attempt_patch.assert_not_called()
        else:
            # If first patch failed, should try again (symbols weren't added to _PATCHED_INTEGRATIONS)
            mock_getter.assert_called_once()
            mock_patcher.attempt_patch.assert_called_once()
        assert ("symbol1" in patch_module._PATCHED_INTEGRATIONS) is success
        assert ("symbol2" in patch_module._PATCHED_INTEGRATIONS) is success
        assert ("symbol3" in patch_module._PATCHED_INTEGRATIONS) is success
