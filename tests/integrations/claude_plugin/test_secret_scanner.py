"""Tests for secret_scanner module."""

import pytest


class TestSecretScanner:
    """Tests for SecretScanner class."""

    def test_scanner_initializes(self):
        """Scanner should initialize without errors."""
        from weave.integrations.claude_plugin.secret_scanner import SecretScanner

        scanner = SecretScanner()
        assert scanner is not None

    def test_scanner_unavailable_when_detect_secrets_missing(self, monkeypatch):
        """get_secret_scanner still works when detect-secrets not installed (AI patterns only)."""
        import sys

        # Remove detect_secrets from modules if present
        modules_to_remove = [k for k in sys.modules if k.startswith('detect_secrets')]
        for mod in modules_to_remove:
            monkeypatch.delitem(sys.modules, mod)

        # Make import fail
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith('detect_secrets'):
                raise ImportError("No module named 'detect_secrets'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, '__import__', mock_import)

        # Need to reload the module to test import behavior
        from weave.integrations.claude_plugin import secret_scanner
        import importlib
        importlib.reload(secret_scanner)

        # Scanner should still be available (AI patterns work without detect-secrets)
        result = secret_scanner.get_secret_scanner()
        assert result is not None
        assert not secret_scanner.DETECT_SECRETS_AVAILABLE
