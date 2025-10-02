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
        patch("weave.integrations.patch.register_import_hook", mock_register_import_hook),
        patch.object(weave_init, "init_weave_get_server") as mock_get_server,
        patch("weave.wandb_interface.context.get_wandb_api_context") as mock_get_context,
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
        patch("weave.trace.settings.should_implicitly_patch_integrations") as mock_should_patch,
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

    with patch("weave.integrations.openai.openai_sdk.get_openai_patcher") as mock_get_patcher:
        mock_patcher = MagicMock()
        mock_patcher.attempt_patch.return_value = True
        mock_get_patcher.return_value = mock_patcher

        patch_openai()

        mock_get_patcher.assert_called_once()
        mock_patcher.attempt_patch.assert_called_once()

        assert "openai" in _PATCHED_INTEGRATIONS


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
