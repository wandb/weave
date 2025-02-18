import os
import pytest

from weave.trace import sanitize, settings


def test_default_redaction():
    """Test the default redaction behavior"""
    assert sanitize.should_redact("api_key")
    assert sanitize.should_redact("API_KEY")
    assert sanitize.should_redact("auth_headers")
    assert sanitize.should_redact("authorization")
    assert not sanitize.should_redact("username")
    assert sanitize.get_redacted_value() == "REDACTED"


def test_custom_redact_keys(monkeypatch):
    """Test customizing which keys get redacted via settings"""
    # Test via settings object
    settings.parse_and_apply_settings({"redact_keys": ("password", "secret_key")})
    assert sanitize.should_redact("password")
    assert sanitize.should_redact("SECRET_KEY")
    assert not sanitize.should_redact("api_key")  # No longer in redact keys

    # Test via environment variable
    monkeypatch.setenv("WEAVE_REDACT_KEYS", "username,email")
    settings.parse_and_apply_settings()  # Reset settings to pick up env vars
    assert sanitize.should_redact("username")
    assert sanitize.should_redact("email")
    assert not sanitize.should_redact("password")


def test_custom_redacted_value(monkeypatch):
    """Test customizing the redacted value via settings"""
    # Test via settings object
    settings.parse_and_apply_settings({"redacted_value": "[HIDDEN]"})
    assert sanitize.get_redacted_value() == "[HIDDEN]"

    # Test via environment variable
    monkeypatch.setenv("WEAVE_REDACTED_VALUE", "***SECRET***")
    settings.parse_and_apply_settings()  # Reset settings to pick up env vars
    assert sanitize.get_redacted_value() == "***SECRET***"


@pytest.fixture(autouse=True)
def cleanup_settings():
    """Reset settings after each test"""
    yield
    # Clear any environment variables we might have set
    for key in ("WEAVE_REDACT_KEYS", "WEAVE_REDACTED_VALUE"):
        if key in os.environ:
            del os.environ[key]
    # Reset settings to defaults
    settings.parse_and_apply_settings() 