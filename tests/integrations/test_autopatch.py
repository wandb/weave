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


# =============================================================================
# WeaveImportHook Tests
# =============================================================================


class TestWeaveImportHook:
    """Tests for the WeaveImportHook class.

    Requirement: Import hook intercepts supported integration imports and wraps
    their loaders to enable automatic patching after module load.
    Interface: Python's import system (sys.meta_path finder protocol)
    """

    def test_find_spec_returns_wrapped_loader_for_supported_root_module(
        self, setup_env, monkeypatch
    ):
        """
        Requirement: Import hook wraps loader for supported integrations
        Interface: WeaveImportHook.find_spec()
        Given: Import hook is registered, "test_integration" is in INTEGRATION_MODULE_MAPPING
        When: find_spec is called for "test_integration"
        Then: Returns a spec with loader wrapped by PatchingLoader
        """
        from weave.integrations.patch import PatchingLoader, WeaveImportHook

        # Create a fake module spec with a loader
        mock_loader = MagicMock()
        mock_spec = MagicMock()
        mock_spec.loader = mock_loader

        # Create a fake finder that will return our spec
        mock_finder = MagicMock()
        mock_finder.find_spec.return_value = mock_spec

        hook = WeaveImportHook()

        # Temporarily add our mock finder to sys.meta_path
        original_meta_path = sys.meta_path.copy()
        sys.meta_path = [mock_finder]

        try:
            with patch.dict(
                "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
                {"test_integration": MagicMock()},
            ):
                result = hook.find_spec("test_integration", None, None)

                assert result is not None
                assert isinstance(result.loader, PatchingLoader)
                assert result.loader.original_loader is mock_loader
                assert result.loader.module_name == "test_integration"
        finally:
            sys.meta_path = original_meta_path

    def test_find_spec_returns_none_for_submodules(self, setup_env, monkeypatch):
        """
        Requirement: Import hook only intercepts root modules, not submodules
        Interface: WeaveImportHook.find_spec()
        Given: Import hook exists, "openai" is in INTEGRATION_MODULE_MAPPING
        When: find_spec is called for "openai.types.chat"
        Then: Returns None (lets normal import proceed without wrapping)
        """
        from weave.integrations.patch import WeaveImportHook

        hook = WeaveImportHook()

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"openai": MagicMock()},
        ):
            # Submodule should not be intercepted
            result = hook.find_spec("openai.types.chat", None, None)
            assert result is None

    def test_find_spec_returns_none_for_unsupported_modules(self, setup_env):
        """
        Requirement: Import hook ignores modules not in INTEGRATION_MODULE_MAPPING
        Interface: WeaveImportHook.find_spec()
        Given: Import hook exists
        When: find_spec is called for "json" (not a supported integration)
        Then: Returns None
        """
        from weave.integrations.patch import WeaveImportHook

        hook = WeaveImportHook()

        # Use empty mapping to ensure "json" is not supported
        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {},
            clear=True,
        ):
            result = hook.find_spec("json", None, None)
            assert result is None

    def test_find_spec_returns_none_for_already_patched_modules(
        self, setup_env, monkeypatch
    ):
        """
        Requirement: Import hook does not re-wrap already patched modules
        Interface: WeaveImportHook.find_spec()
        Given: Import hook exists, "openai" is already in _PATCHED_INTEGRATIONS
        When: find_spec is called for "openai"
        Then: Returns None (no need to wrap, already patched)
        """
        from weave.integrations.patch import WeaveImportHook

        # Mark openai as already patched
        patch_module._PATCHED_INTEGRATIONS.add("openai")

        hook = WeaveImportHook()

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"openai": MagicMock()},
        ):
            result = hook.find_spec("openai", None, None)
            assert result is None

    def test_find_module_returns_none_for_backwards_compatibility(self, setup_env):
        """
        Requirement: Legacy find_module method returns None for backwards compatibility
        Interface: WeaveImportHook.find_module()
        Given: Import hook instance
        When: find_module is called with any module name
        Then: Returns None
        """
        from weave.integrations.patch import WeaveImportHook

        hook = WeaveImportHook()

        assert hook.find_module("anything") is None
        assert hook.find_module("openai", path="/some/path") is None


# =============================================================================
# PatchingLoader Tests
# =============================================================================


class TestPatchingLoader:
    """Tests for the PatchingLoader class.

    Requirement: PatchingLoader wraps original loaders and patches integrations
    after module execution completes.
    Interface: Python's import system (loader protocol)
    """

    def test_exec_module_calls_original_and_patches(self, setup_env):
        """
        Requirement: exec_module executes original loader then patches integration
        Interface: PatchingLoader.exec_module()
        Given: PatchingLoader wrapping an original loader
        When: exec_module is called
        Then: Original loader's exec_module is called, then patch function is invoked
        """
        from weave.integrations.patch import PatchingLoader

        mock_original_loader = MagicMock()
        mock_patch_func = MagicMock()

        loader = PatchingLoader(mock_original_loader, "test_module")

        mock_module = MagicMock()
        mock_module.__name__ = "test_module"

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"test_module": mock_patch_func},
        ):
            loader.exec_module(mock_module)

            # Original loader should be called first
            mock_original_loader.exec_module.assert_called_once_with(mock_module)
            # Then patch function should be called
            mock_patch_func.assert_called_once()

    def test_exec_module_does_not_patch_non_root_modules(self, setup_env):
        """
        Requirement: exec_module only patches when module name matches
        Interface: PatchingLoader.exec_module()
        Given: PatchingLoader configured for "openai"
        When: exec_module is called with a module named "openai.types"
        Then: Patch function is NOT called
        """
        from weave.integrations.patch import PatchingLoader

        mock_original_loader = MagicMock()
        mock_patch_func = MagicMock()

        loader = PatchingLoader(mock_original_loader, "openai")

        mock_module = MagicMock()
        mock_module.__name__ = "openai.types"  # Submodule, not root

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"openai": mock_patch_func},
        ):
            loader.exec_module(mock_module)

            mock_original_loader.exec_module.assert_called_once()
            mock_patch_func.assert_not_called()

    def test_load_module_calls_original_and_patches(self, setup_env, monkeypatch):
        """
        Requirement: Legacy load_module executes original loader then patches
        Interface: PatchingLoader.load_module()
        Given: PatchingLoader wrapping a loader with load_module method
        When: load_module is called
        Then: Original loader's load_module is called, then patch function is invoked
        """
        from weave.integrations.patch import PatchingLoader

        mock_original_loader = MagicMock()
        mock_module = MagicMock()
        mock_original_loader.load_module.return_value = mock_module
        mock_patch_func = MagicMock()

        loader = PatchingLoader(mock_original_loader, "test_module")

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"test_module": mock_patch_func},
        ):
            result = loader.load_module("test_module")

            mock_original_loader.load_module.assert_called_once_with("test_module")
            mock_patch_func.assert_called_once()
            assert result is mock_module

    def test_load_module_fallback_when_no_load_module(self, setup_env, monkeypatch):
        """
        Requirement: load_module falls back to sys.modules when original has no load_module
        Interface: PatchingLoader.load_module()
        Given: PatchingLoader wrapping a loader without load_module method
        When: load_module is called and module is in sys.modules
        Then: Returns the module from sys.modules
        """
        from weave.integrations.patch import PatchingLoader

        # Create a loader without load_module
        mock_original_loader = MagicMock(spec=[])  # Empty spec = no methods
        mock_patch_func = MagicMock()

        loader = PatchingLoader(mock_original_loader, "test_module")

        # Put a fake module in sys.modules
        fake_module = types.ModuleType("test_module")
        monkeypatch.setitem(sys.modules, "test_module", fake_module)

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {"test_module": mock_patch_func},
        ):
            result = loader.load_module("test_module")

            assert result is fake_module
            mock_patch_func.assert_called_once()

    def test_create_module_delegates_to_original(self, setup_env):
        """
        Requirement: create_module delegates to original loader
        Interface: PatchingLoader.create_module()
        Given: PatchingLoader wrapping a loader with create_module method
        When: create_module is called
        Then: Original loader's create_module is called and result returned
        """
        from weave.integrations.patch import PatchingLoader

        mock_original_loader = MagicMock()
        mock_spec = MagicMock()
        mock_created_module = MagicMock()
        mock_original_loader.create_module.return_value = mock_created_module

        loader = PatchingLoader(mock_original_loader, "test_module")

        result = loader.create_module(mock_spec)

        mock_original_loader.create_module.assert_called_once_with(mock_spec)
        assert result is mock_created_module

    def test_create_module_returns_none_when_original_lacks_method(self, setup_env):
        """
        Requirement: create_module returns None when original has no create_module
        Interface: PatchingLoader.create_module()
        Given: PatchingLoader wrapping a loader without create_module method
        When: create_module is called
        Then: Returns None (default behavior)
        """
        from weave.integrations.patch import PatchingLoader

        # Create a loader without create_module
        mock_original_loader = MagicMock(spec=[])

        loader = PatchingLoader(mock_original_loader, "test_module")

        result = loader.create_module(MagicMock())

        assert result is None

    def test_getattr_delegates_to_original(self, setup_env):
        """
        Requirement: Unknown attributes are delegated to original loader
        Interface: PatchingLoader.__getattr__()
        Given: PatchingLoader wrapping a loader with custom attributes
        When: Accessing an attribute not defined on PatchingLoader
        Then: Returns the attribute from the original loader
        """
        from weave.integrations.patch import PatchingLoader

        mock_original_loader = MagicMock()
        mock_original_loader.custom_attribute = "custom_value"
        mock_original_loader.some_method.return_value = "method_result"

        loader = PatchingLoader(mock_original_loader, "test_module")

        assert loader.custom_attribute == "custom_value"
        assert loader.some_method() == "method_result"


# =============================================================================
# Integration Tests - Real Import System
# =============================================================================


class TestImportHookIntegration:
    """Integration tests for the import hook mechanism with Python's real import system.

    Requirement: The import hook correctly integrates with Python's import machinery
    to automatically patch supported integrations when they are imported.
    Interface: The full import chain (sys.meta_path -> WeaveImportHook -> PatchingLoader)
    """

    def test_full_import_hook_workflow_patches_on_real_import(
        self, setup_env, monkeypatch
    ):
        """
        Requirement: Import hook patches integrations when they are imported
        Interface: Full import system integration
        Given: Import hook is registered, test module mapped to mock patcher
        When: A fresh module is imported via the import system
        Then: Patch function is called exactly once after import completes
        """
        # Create a unique test module name to avoid conflicts
        test_module_name = "_weave_test_import_hook_module"

        # Remove it from sys.modules if it exists
        if test_module_name in sys.modules:
            del sys.modules[test_module_name]

        # Track patch calls
        patch_calls = []

        def mock_patch_func():
            patch_calls.append(1)

        register_import_hook()

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {test_module_name: mock_patch_func},
        ):
            # Create and inject a fake module to simulate import
            fake_module = types.ModuleType(test_module_name)
            monkeypatch.setitem(sys.modules, test_module_name, fake_module)

            # Trigger the patch via _patch_if_needed (simulating what the loader does)
            from weave.integrations.patch import _patch_if_needed

            _patch_if_needed(test_module_name)

            assert len(patch_calls) == 1

    def test_import_hook_does_not_patch_when_already_patched(
        self, setup_env, monkeypatch
    ):
        """
        Requirement: Import hook respects already-patched state
        Interface: Full import system integration
        Given: Import hook registered, module already marked as patched
        When: Module is "imported" again
        Then: Patch function is NOT called again
        """
        test_module_name = "_weave_test_already_patched_module"

        patch_calls = []

        def mock_patch_func():
            patch_calls.append(1)

        # Mark as already patched
        patch_module._PATCHED_INTEGRATIONS.add(test_module_name)

        register_import_hook()

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {test_module_name: mock_patch_func},
        ):
            fake_module = types.ModuleType(test_module_name)
            monkeypatch.setitem(sys.modules, test_module_name, fake_module)

            from weave.integrations.patch import _patch_if_needed

            _patch_if_needed(test_module_name)

            # Should not be called since module is already patched
            assert len(patch_calls) == 0

    def test_import_hook_handles_patch_failure_gracefully(self, setup_env, monkeypatch):
        """
        Requirement: Import hook handles patch failures gracefully
        Interface: Full import system integration
        Given: Import hook registered, patch function raises an exception
        When: Module is imported
        Then: Exception is caught and does not propagate
        """
        test_module_name = "_weave_test_failing_patch_module"

        if test_module_name in sys.modules:
            del sys.modules[test_module_name]

        def failing_patch_func():
            raise RuntimeError("Patch failed!")

        register_import_hook()

        with patch.dict(
            "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
            {test_module_name: failing_patch_func},
        ):
            fake_module = types.ModuleType(test_module_name)
            monkeypatch.setitem(sys.modules, test_module_name, fake_module)

            from weave.integrations.patch import _patch_if_needed

            # Should not raise - failures are handled gracefully
            _patch_if_needed(test_module_name)

            # Module should NOT be in patched integrations (patch failed)
            assert test_module_name not in patch_module._PATCHED_INTEGRATIONS

    def test_weave_import_hook_find_spec_skips_self(self, setup_env):
        """
        Requirement: Import hook does not recurse infinitely by skipping itself
        Interface: WeaveImportHook.find_spec()
        Given: Import hook is in sys.meta_path
        When: find_spec iterates through meta_path
        Then: It skips itself to avoid infinite recursion
        """
        from weave.integrations.patch import WeaveImportHook

        hook = WeaveImportHook()
        mock_finder = MagicMock()
        mock_spec = MagicMock()
        mock_spec.loader = MagicMock()
        mock_finder.find_spec.return_value = mock_spec

        # Put hook first in meta_path, then mock finder
        original_meta_path = sys.meta_path.copy()
        sys.meta_path = [hook, mock_finder]

        try:
            with patch.dict(
                "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
                {"test_module": MagicMock()},
            ):
                result = hook.find_spec("test_module", None, None)

                # Should get result from mock_finder, not recurse into hook
                assert result is not None
                mock_finder.find_spec.assert_called_once()
        finally:
            sys.meta_path = original_meta_path
