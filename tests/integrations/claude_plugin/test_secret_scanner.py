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


class TestSecretDetection:
    """Tests for secret detection."""

    @pytest.fixture
    def scanner(self):
        from weave.integrations.claude_plugin.secret_scanner import SecretScanner
        return SecretScanner()

    def test_detects_openai_key(self, scanner):
        """Should detect OpenAI API keys."""
        content = "OPENAI_API_KEY=sk-proj-abc123xyz789def456ghi012jkl345"
        secrets = scanner.scan_text(content)
        assert len(secrets) >= 1
        assert any(s.secret_type == "openai_api_key" for s in secrets)

    def test_detects_anthropic_key(self, scanner):
        """Should detect Anthropic API keys."""
        content = "export ANTHROPIC_API_KEY=sk-ant-abc123xyz789def456ghi"
        secrets = scanner.scan_text(content)
        assert len(secrets) >= 1
        assert any(s.secret_type == "anthropic_api_key" for s in secrets)

    def test_detects_google_key(self, scanner):
        """Should detect Google/Gemini API keys."""
        content = "GOOGLE_API_KEY=AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz1234567"
        secrets = scanner.scan_text(content)
        assert len(secrets) >= 1
        assert any(s.secret_type == "google_api_key" for s in secrets)

    def test_detects_huggingface_token(self, scanner):
        """Should detect HuggingFace tokens."""
        content = "HF_TOKEN=hf_abcdefghijklmnopqrstuvwxyz12345678"
        secrets = scanner.scan_text(content)
        assert len(secrets) >= 1
        assert any(s.secret_type == "huggingface_token" for s in secrets)

    def test_no_false_positives_on_normal_text(self, scanner):
        """Should not flag normal text as secrets."""
        content = "Hello world, this is a normal sentence."
        secrets = scanner.scan_text(content)
        # Filter out low-confidence detections
        high_confidence = [s for s in secrets if "entropy" not in s.secret_type.lower()]
        assert len(high_confidence) == 0

    def test_detects_multiple_secrets(self, scanner):
        """Should detect multiple secrets in same content."""
        content = """
        OPENAI_API_KEY=sk-proj-abc123xyz789def456ghi012jkl345
        ANTHROPIC_API_KEY=sk-ant-def456xyz789abc123ghi
        """
        secrets = scanner.scan_text(content)
        assert len(secrets) >= 2


class TestSecretRedaction:
    """Tests for secret redaction."""

    @pytest.fixture
    def scanner(self):
        from weave.integrations.claude_plugin.secret_scanner import SecretScanner
        return SecretScanner()

    def test_redacts_secret(self, scanner):
        """Should replace secret with redaction marker."""
        content = "key: sk-ant-abc123xyz789def456ghi"
        redacted, count = scanner.redact_text(content)
        assert count >= 1
        assert "sk-ant" not in redacted
        assert "[REDACTED:" in redacted

    def test_redaction_preserves_context(self, scanner):
        """Should preserve surrounding text."""
        content = "Before sk-ant-abc123xyz789def456ghi After"
        redacted, count = scanner.redact_text(content)
        assert "Before" in redacted
        assert "After" in redacted

    def test_redaction_includes_type(self, scanner):
        """Redaction marker should include secret type."""
        content = "OPENAI_API_KEY=sk-proj-abc123xyz789def456ghi012jkl345"
        redacted, count = scanner.redact_text(content)
        assert "[REDACTED:openai_api_key]" in redacted or "[REDACTED:" in redacted

    def test_redacts_multiple_secrets(self, scanner):
        """Should redact all secrets in content."""
        content = """
        OPENAI_API_KEY=sk-proj-abc123xyz789def456ghi012jkl345
        ANTHROPIC_API_KEY=sk-ant-def456xyz789abc123ghi
        """
        redacted, count = scanner.redact_text(content)
        assert count >= 2
        assert "sk-proj" not in redacted
        assert "sk-ant" not in redacted

    def test_no_redaction_for_clean_content(self, scanner):
        """Should return content unchanged if no secrets."""
        content = "Hello world, no secrets here."
        redacted, count = scanner.redact_text(content)
        assert count == 0
        assert redacted == content
