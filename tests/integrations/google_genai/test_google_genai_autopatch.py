"""Tests for Google GenAI autopatching behavior."""

from unittest.mock import MagicMock, patch

from weave.integrations.patch import register_import_hook


def test_google_genai_autopatch():
    register_import_hook()
    mock_patch_func = MagicMock()

    with patch.dict(
        "weave.integrations.patch.INTEGRATION_MODULE_MAPPING",
        {"google.genai": mock_patch_func},
    ):
        import google.genai  # noqa: F401

    mock_patch_func.assert_called_once()
