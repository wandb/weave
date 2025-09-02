"""Tests for automatic integration patching.

This test module validates the automatic patching mechanism that Weave uses to
transparently instrument supported libraries. The autopatching system works in
two ways:

1. Implicit Patching: When weave.init() is called, it:
   - Patches any already-imported supported libraries via implicit_patch()
   - Registers an import hook that patches libraries imported after init

2. Explicit Patching: When autopatching is disabled, users must manually call
   patch functions like weave.integrations.patch_openai()

The tests verify:
- Already-imported modules are patched by implicit_patch()
- The import hook patches modules imported after weave.init()
- Settings to disable autopatching are respected
- Import hook registration and cleanup work correctly
- Multiple integrations can be patched
- Double-patching is prevented
- Patch failures are handled gracefully
"""

import copy
import sys
from collections.abc import Generator

import pytest

from weave.integrations.patch import (
    _IMPORT_HOOK,
    _PATCHED_INTEGRATIONS,
    INTEGRATION_MODULE_MAPPING,
    WeaveImportHook,
    implicit_patch,
    register_import_hook,
    unregister_import_hook,
)
from weave.trace import weave_init


@pytest.fixture
def clean_patching_state() -> Generator[None, None, None]:
    """Clean up patching state before and after tests."""
    original_patched = copy.deepcopy(_PATCHED_INTEGRATIONS)
    original_hook = _IMPORT_HOOK
    original_meta_path = sys.meta_path.copy()

    # Clear state
    _PATCHED_INTEGRATIONS.clear()
    unregister_import_hook()

    yield

    # Restore state
    _PATCHED_INTEGRATIONS.clear()
    _PATCHED_INTEGRATIONS.update(original_patched)
    unregister_import_hook()
    sys.meta_path[:] = original_meta_path
    if original_hook is not None:
        from weave.integrations import patch as patch_module

        patch_module._IMPORT_HOOK = original_hook


@pytest.fixture
def mock_openai_module(monkeypatch) -> object:
    """Mock the openai module for testing."""

    class MockModule:
        __name__ = "openai"

    mock_module = MockModule()

    # Temporarily add to sys.modules
    monkeypatch.setitem(sys.modules, "openai", mock_module)

    return mock_module  # monkeypatch automatically cleans up


@pytest.fixture
def mock_anthropic_module(monkeypatch) -> object:
    """Mock the anthropic module for testing."""

    class MockModule:
        __name__ = "anthropic"

    mock_module = MockModule()

    # Temporarily add to sys.modules
    monkeypatch.setitem(sys.modules, "anthropic", mock_module)

    return mock_module  # monkeypatch automatically cleans up


def test_implicit_patch_already_imported_modules(
    clean_patching_state, mock_openai_module, client, monkeypatch
):
    """Test that implicit_patch patches already-imported modules."""
    # Ensure module is in sys.modules but not patched
    assert "openai" in sys.modules
    assert "openai" not in _PATCHED_INTEGRATIONS

    # Mock the patch function
    patch_called = []

    def mock_patch_openai():
        patch_called.append(True)
        _PATCHED_INTEGRATIONS.add("openai")

    monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

    # Run implicit patch
    implicit_patch()

    # Verify patch was called
    assert len(patch_called) == 1
    assert "openai" in _PATCHED_INTEGRATIONS


def test_implicit_patch_respects_settings(
    clean_patching_state, mock_openai_module, client, monkeypatch
):
    """Test that implicit_patch respects the implicitly_patch_integrations setting."""
    # Ensure module is in sys.modules but not patched
    assert "openai" in sys.modules
    assert "openai" not in _PATCHED_INTEGRATIONS

    # Mock the settings to disable implicit patching
    monkeypatch.setattr(
        "weave.trace.settings.should_implicitly_patch_integrations", lambda: False
    )

    patch_called = []

    def mock_patch_openai():
        patch_called.append(True)

    monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

    # Run implicit patch
    implicit_patch()

    # Verify patch was NOT called
    assert len(patch_called) == 0
    assert "openai" not in _PATCHED_INTEGRATIONS


def test_register_import_hook(clean_patching_state, client):
    """Test that register_import_hook installs the import hook."""
    # Verify hook is not installed
    assert not any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)

    # Register the hook
    register_import_hook()

    # Verify hook is installed
    assert any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)
    # Should be at the beginning of meta_path
    assert isinstance(sys.meta_path[0], WeaveImportHook)


def test_register_import_hook_respects_settings(
    clean_patching_state, client, monkeypatch
):
    """Test that register_import_hook respects the implicitly_patch_integrations setting."""
    # Mock the settings to disable implicit patching
    monkeypatch.setattr(
        "weave.trace.settings.should_implicitly_patch_integrations", lambda: False
    )

    # Register the hook
    register_import_hook()

    # Verify hook is NOT installed
    assert not any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)


def test_unregister_import_hook(clean_patching_state, client):
    """Test that unregister_import_hook removes the import hook."""
    # Register the hook first
    register_import_hook()
    assert any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)

    # Unregister the hook
    unregister_import_hook()

    # Verify hook is removed
    assert not any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)


def test_import_hook_patches_on_import(clean_patching_state, client, monkeypatch):
    """Test that the import hook patches modules when they are imported."""
    # Register the import hook
    register_import_hook()

    # Ensure openai is not imported or patched
    if "openai" in sys.modules:
        del sys.modules["openai"]
    assert "openai" not in _PATCHED_INTEGRATIONS

    # Mock the patch function
    patch_called = []

    def mock_patch_openai():
        patch_called.append(True)
        _PATCHED_INTEGRATIONS.add("openai")

    monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

    # Since we're mocking the import process, we need to manually trigger
    # what would happen in the PatchingLoader
    from weave.integrations.patch import _patch_if_needed

    _patch_if_needed("openai")

    # Verify patch was called
    assert len(patch_called) == 1
    assert "openai" in _PATCHED_INTEGRATIONS


def test_weave_init_enables_autopatching(
    clean_patching_state, trace_server, monkeypatch
):
    """Test that weave.init() enables automatic patching by default."""

    # Mock the openai module
    class MockModule:
        __name__ = "openai"

    mock_module = MockModule()
    monkeypatch.setitem(sys.modules, "openai", mock_module)

    try:
        patch_called = []

        def mock_patch_openai():
            patch_called.append(True)
            _PATCHED_INTEGRATIONS.add("openai")

        monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

        # Initialize weave
        client = weave_init.init_weave("test-project", ensure_project_exists=False)

        # Verify implicit_patch was called (openai was already imported)
        assert len(patch_called) == 1

        # Verify import hook is registered
        assert any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)
    finally:
        # Clean up the global client
        from weave.trace.context import weave_client_context

        weave_client_context.set_weave_client_global(None)


def test_weave_init_with_disabled_autopatching(
    clean_patching_state, trace_server, monkeypatch
):
    """Test that weave.init() respects disabled autopatching setting."""

    # Mock the openai module
    class MockModule:
        __name__ = "openai"

    mock_module = MockModule()
    monkeypatch.setitem(sys.modules, "openai", mock_module)

    try:
        # Set the setting to disable implicit patching
        monkeypatch.setattr(
            "weave.trace.settings.should_implicitly_patch_integrations", lambda: False
        )

        patch_called = []

        def mock_patch_openai():
            patch_called.append(True)

        monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

        # Initialize weave
        client = weave_init.init_weave("test-project", ensure_project_exists=False)

        # Verify implicit_patch was NOT called
        assert len(patch_called) == 0

        # Verify import hook is NOT registered
        assert not any(isinstance(finder, WeaveImportHook) for finder in sys.meta_path)
    finally:
        # Clean up the global client
        from weave.trace.context import weave_client_context

        weave_client_context.set_weave_client_global(None)


def test_multiple_integrations_patched(
    clean_patching_state, mock_openai_module, mock_anthropic_module, client, monkeypatch
):
    """Test that multiple integrations can be patched."""
    # Ensure modules are in sys.modules but not patched
    assert "openai" in sys.modules
    assert "anthropic" in sys.modules
    assert "openai" not in _PATCHED_INTEGRATIONS
    assert "anthropic" not in _PATCHED_INTEGRATIONS

    # Mock the patch functions
    openai_patched = []
    anthropic_patched = []

    def mock_patch_openai():
        openai_patched.append(True)
        _PATCHED_INTEGRATIONS.add("openai")

    def mock_patch_anthropic():
        anthropic_patched.append(True)
        _PATCHED_INTEGRATIONS.add("anthropic")

    monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)
    monkeypatch.setattr(
        "weave.integrations.patch.patch_anthropic", mock_patch_anthropic
    )

    # Run implicit patch
    implicit_patch()

    # Verify both patches were called
    assert len(openai_patched) == 1
    assert len(anthropic_patched) == 1
    assert "openai" in _PATCHED_INTEGRATIONS
    assert "anthropic" in _PATCHED_INTEGRATIONS


def test_double_patching_prevented(
    clean_patching_state, mock_openai_module, client, monkeypatch
):
    """Test that modules are not patched twice."""
    patch_count = []

    def mock_patch_openai():
        patch_count.append(True)
        _PATCHED_INTEGRATIONS.add("openai")

    monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

    # First patch
    implicit_patch()
    assert len(patch_count) == 1
    assert "openai" in _PATCHED_INTEGRATIONS

    # Second patch attempt
    implicit_patch()
    # Should not be called again
    assert len(patch_count) == 1  # Still only 1 call
    assert "openai" in _PATCHED_INTEGRATIONS


def test_patch_failure_handled_gracefully(
    clean_patching_state, mock_openai_module, client, monkeypatch
):
    """Test that patch failures are handled gracefully."""
    # Ensure module is in sys.modules but not patched
    assert "openai" in sys.modules
    assert "openai" not in _PATCHED_INTEGRATIONS

    # Mock the patch function to raise an exception
    def mock_patch_openai():
        raise RuntimeError("Patch failed")

    monkeypatch.setattr("weave.integrations.patch.patch_openai", mock_patch_openai)

    # Run implicit patch - should not raise
    implicit_patch()

    # Module should still be marked as patched to prevent retries
    assert "openai" in _PATCHED_INTEGRATIONS


def test_import_hook_with_submodules(clean_patching_state, client, monkeypatch):
    """Test that the import hook correctly handles submodules."""
    # Register the import hook
    register_import_hook()

    # Create mocks for google.generativeai
    class MockGoogle:
        class Generativeai:  # Use CapWords for class name
            pass

    mock_google = MockGoogle()
    monkeypatch.setitem(sys.modules, "google", mock_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", mock_google.Generativeai)

    patch_called = []

    def mock_patch():
        patch_called.append(True)
        _PATCHED_INTEGRATIONS.add("google.generativeai")

    monkeypatch.setattr("weave.integrations.patch.patch_google_genai", mock_patch)

    # Trigger the patching mechanism for google.generativeai
    from weave.integrations.patch import _patch_if_needed

    _patch_if_needed("google.generativeai")

    # Verify the patch was called for google.generativeai
    assert len(patch_called) == 1
    assert "google.generativeai" in _PATCHED_INTEGRATIONS


def test_all_mapped_integrations_have_patch_functions(clean_patching_state):
    """Test that all integrations in INTEGRATION_MODULE_MAPPING have valid patch functions."""
    for module_name, patch_func in INTEGRATION_MODULE_MAPPING.items():
        # Verify the patch function is callable
        assert callable(patch_func), f"Patch function for {module_name} is not callable"

        # Verify the patch function name follows convention
        expected_func_name = f"patch_{module_name.replace('.', '_').replace('_', '_')}"
        # Some special cases don't follow exact naming convention
        special_cases = {
            "google.generativeai": "patch_google_genai",
            "vertexai": "patch_vertexai",
            "huggingface_hub": "patch_huggingface",
            "langchain_nvidia_ai_endpoints": "patch_nvidia",
            "crewai_tools": "patch_crewai",
            "openai_agents": "patch_openai_agents",
            "llama_index": "patch_llamaindex",
        }

        if module_name not in special_cases:
            # For regular cases, just check that it has "patch" in the name
            assert "patch" in patch_func.__name__.lower(), (
                f"Patch function for {module_name} doesn't follow naming convention"
            )
