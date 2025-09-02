"""Tests for the automatic patching mechanism."""

from __future__ import annotations

import sys
import types
from typing import Any, cast
from unittest import mock

import pytest

from weave.integrations.patch import (
    implicit_patch,
    register_import_hook,
    reset_patched_integrations,
    unregister_import_hook,
)


def _reset_import(monkeypatch, module: str):
    """Helper to reset a module import."""
    if module in sys.modules:
        monkeypatch.delitem(sys.modules, module, raising=False)


def _inject_fake_module(monkeypatch, module_name: str):
    """Inject a fake module into sys.modules."""
    m = cast(Any, types.ModuleType(module_name))

    # Add some dummy attributes to make it look like a real integration
    m.Client = type("Client", (), {})
    m.__version__ = "1.0.0"

    monkeypatch.setitem(sys.modules, module_name, m)
    return m


@pytest.fixture
def setup_env(monkeypatch):
    """Reset the environment for each test."""
    # Clear any existing patches - this creates a new set
    reset_patched_integrations()

    # Unregister any existing import hook
    unregister_import_hook()

    # Clear environment variables
    monkeypatch.delenv("WEAVE_IMPLICITLY_PATCH_INTEGRATIONS", raising=False)
    monkeypatch.delenv("WEAVE_DISABLED", raising=False)

    # Reset imports for common integrations
    for module in ["openai", "anthropic", "mistralai", "groq", "litellm"]:
        _reset_import(monkeypatch, module)

    yield

    # Cleanup after test
    reset_patched_integrations()
    unregister_import_hook()


def test_implicit_patch_already_imported(setup_env, monkeypatch):
    """Test that implicit_patch patches libraries that are already imported."""
    # Inject fake openai module
    _inject_fake_module(monkeypatch, "openai")

    # Create a mock patch function
    mock_patch_func = mock.MagicMock()

    # Mock the mapping to use our mock function
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # Call implicit_patch (normally called during weave.init())
        implicit_patch()

        # Verify that patch function was called
        mock_patch_func.assert_called_once()


def test_implicit_patch_multiple_libraries(setup_env, monkeypatch):
    """Test that implicit_patch patches multiple already-imported libraries."""
    # Inject multiple fake modules
    _inject_fake_module(monkeypatch, "openai")
    _inject_fake_module(monkeypatch, "anthropic")
    _inject_fake_module(monkeypatch, "mistralai")

    # Create mock patch functions
    mock_patch_openai = mock.MagicMock()
    mock_patch_anthropic = mock.MagicMock()
    mock_patch_mistral = mock.MagicMock()

    # Mock the mapping to use our mock functions
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {
            "openai": mock_patch_openai,
            "anthropic": mock_patch_anthropic,
            "mistralai": mock_patch_mistral,
        },
    ):
        # Call implicit_patch
        implicit_patch()

        # Verify all patch functions were called
        mock_patch_openai.assert_called_once()
        mock_patch_anthropic.assert_called_once()
        mock_patch_mistral.assert_called_once()


def test_implicit_patch_disabled(setup_env, monkeypatch):
    """Test that implicit patching can be disabled via environment variable."""
    # Disable implicit patching
    monkeypatch.setenv("WEAVE_IMPLICITLY_PATCH_INTEGRATIONS", "false")

    # Inject fake openai module
    _inject_fake_module(monkeypatch, "openai")

    # Create a mock patch function
    mock_patch_func = mock.MagicMock()

    # Mock the mapping to use our mock function
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # Call implicit_patch
        implicit_patch()

        # Verify that patch function was NOT called
        mock_patch_func.assert_not_called()


def test_import_hook_patches_on_import(setup_env, monkeypatch):
    """Test that the import hook patches libraries when they are imported after weave.init()."""
    # Register the import hook (normally done during weave.init())
    register_import_hook()

    # Create a mock patch function
    mock_patch_func = mock.MagicMock()

    # Mock the mapping to use our mock function
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # Import openai after hook registration
        # We need to inject it as it's imported
        _inject_fake_module(monkeypatch, "openai")

        # Simulate the import hook being triggered
        # In reality, this happens automatically via sys.meta_path
        from weave.integrations.patch import _patch_if_needed

        _patch_if_needed("openai")

        # Verify that patch function was called
        mock_patch_func.assert_called_once()


def test_import_hook_disabled(setup_env, monkeypatch):
    """Test that import hook is not registered when implicit patching is disabled."""
    # Disable implicit patching
    monkeypatch.setenv("WEAVE_IMPLICITLY_PATCH_INTEGRATIONS", "false")

    # Try to register the import hook
    register_import_hook()

    # Verify hook was not registered
    from weave.integrations.patch import _IMPORT_HOOK

    assert _IMPORT_HOOK is None


def test_no_double_patching(setup_env, monkeypatch):
    """Test that libraries are not patched multiple times."""
    from weave.integrations.patch import _PATCHED_INTEGRATIONS

    # Inject fake openai module
    _inject_fake_module(monkeypatch, "openai")

    # Create a mock patch function
    mock_patch_func = mock.MagicMock()

    # Mock the mapping to use our mock function
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # First implicit_patch call
        implicit_patch()
        assert mock_patch_func.call_count == 1

        # Manually mark as patched (simulating successful patch)
        _PATCHED_INTEGRATIONS.add("openai")

        # Second implicit_patch call should not patch again
        implicit_patch()
        assert mock_patch_func.call_count == 1  # Still only called once


def test_patch_failure_graceful(setup_env, monkeypatch):
    """Test that patching failures are handled gracefully."""
    # Inject fake openai module
    _inject_fake_module(monkeypatch, "openai")

    # Create a mock patch function that raises an exception
    mock_patch_func = mock.MagicMock(side_effect=Exception("Patch failed"))

    # Mock the mapping to use our mock function
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # Call implicit_patch - should not raise
        implicit_patch()

        # Verify that patch function was called but failed gracefully
        mock_patch_func.assert_called_once()


def test_init_weave_calls_patching(setup_env, monkeypatch):
    """Test that init_weave calls implicit_patch and register_import_hook."""
    # Track whether patching functions were called
    patch_calls = {"implicit_patch": 0, "register_import_hook": 0}

    def mock_implicit_patch():
        patch_calls["implicit_patch"] += 1

    def mock_register_import_hook():
        patch_calls["register_import_hook"] += 1

    # Mock the patching functions BEFORE importing weave_init
    with (
        mock.patch("weave.integrations.patch.implicit_patch", mock_implicit_patch),
        mock.patch(
            "weave.integrations.patch.register_import_hook", mock_register_import_hook
        ),
    ):
        # Now import weave_init - it will import the mocked functions
        from weave.trace import weave_init

        # Mock the parts that would fail in test environment
        with (
            mock.patch.object(weave_init, "init_weave_get_server") as mock_get_server,
            mock.patch(
                "weave.wandb_interface.context.get_wandb_api_context"
            ) as mock_get_context,
            mock.patch.object(weave_init, "get_username") as mock_get_username,
            mock.patch(
                "weave.trace.init_message.print_init_message"
            ) as mock_print_message,
        ):
            # Setup mocks
            mock_get_context.return_value = mock.MagicMock(api_key="test_key")
            mock_server = mock.MagicMock()
            mock_server.server_info.return_value.min_required_weave_python_version = (
                "0.0.0"
            )
            mock_get_server.return_value = mock_server
            mock_get_username.return_value = "test_user"

            # Call init_weave directly
            client = weave_init.init_weave("test_entity/test_project")

            # Verify patching functions were called
            assert patch_calls["implicit_patch"] == 1
            assert patch_calls["register_import_hook"] == 1

            # Clean up
            if client:
                try:
                    client.finish()
                except Exception:
                    pass


def test_implicit_patching_disabled_via_settings(setup_env, monkeypatch):
    """Test that implicit patching can be disabled via settings."""
    # Inject fake module
    _inject_fake_module(monkeypatch, "openai")

    # Create a mock patch function
    mock_patch_func = mock.MagicMock()

    # Mock the mapping to track patch calls
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # Mock should_implicitly_patch_integrations to return False
        with mock.patch(
            "weave.trace.settings.should_implicitly_patch_integrations"
        ) as mock_should_patch:
            mock_should_patch.return_value = False

            # Call implicit_patch
            implicit_patch()

            # Verify that patch function was NOT called
            mock_patch_func.assert_not_called()

            # Also test register_import_hook
            register_import_hook()

            # Verify hook was not registered
            from weave.integrations.patch import _IMPORT_HOOK

            assert _IMPORT_HOOK is None


def test_patch_if_needed(setup_env, monkeypatch):
    """Test the _patch_if_needed helper function."""
    from weave.integrations.patch import _PATCHED_INTEGRATIONS, _patch_if_needed

    # Inject fake openai module
    _inject_fake_module(monkeypatch, "openai")

    # Create a mock patch function
    mock_patch_func = mock.MagicMock()

    # Mock the mapping to use our mock function
    with mock.patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"openai": mock_patch_func},
    ):
        # First call should patch
        _patch_if_needed("openai")
        mock_patch_func.assert_called_once()

        # Mark as patched
        _PATCHED_INTEGRATIONS.add("openai")

        # Second call should not patch again
        mock_patch_func.reset_mock()
        _patch_if_needed("openai")
        mock_patch_func.assert_not_called()


def test_explicit_patch_still_works(setup_env, monkeypatch):
    """Test that explicit patching still works alongside implicit patching."""
    from weave.integrations.patch import _PATCHED_INTEGRATIONS

    # Inject fake openai module
    _inject_fake_module(monkeypatch, "openai")

    # Mock the actual patcher
    with mock.patch(
        "weave.integrations.openai.openai_sdk.get_openai_patcher"
    ) as mock_get_patcher:
        mock_patcher = mock.MagicMock()
        mock_patcher.attempt_patch.return_value = True
        mock_get_patcher.return_value = mock_patcher

        # Explicitly patch
        from weave.integrations.patch import patch_openai

        patch_openai()

        # Verify patcher was called
        mock_get_patcher.assert_called_once()
        mock_patcher.attempt_patch.assert_called_once()

        # Verify integration marked as patched
        assert "openai" in _PATCHED_INTEGRATIONS


def test_reset_patched_integrations(setup_env, monkeypatch):
    """Test that reset_patched_integrations clears the patched set."""
    import weave.integrations.patch as patch_module

    # Add some integrations to the patched set
    patch_module._PATCHED_INTEGRATIONS.add("openai")
    patch_module._PATCHED_INTEGRATIONS.add("anthropic")

    assert len(patch_module._PATCHED_INTEGRATIONS) == 2

    # Reset
    reset_patched_integrations()

    # Get the new reference after reset
    assert len(patch_module._PATCHED_INTEGRATIONS) == 0


def test_unregister_import_hook(setup_env):
    """Test that unregister_import_hook removes the hook from sys.meta_path."""
    # Register the hook
    register_import_hook()

    from weave.integrations.patch import _IMPORT_HOOK

    assert _IMPORT_HOOK is not None
    assert _IMPORT_HOOK in sys.meta_path

    # Unregister
    unregister_import_hook()

    from weave.integrations.patch import _IMPORT_HOOK

    assert _IMPORT_HOOK is None
