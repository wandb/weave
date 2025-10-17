"""Tests for PII redaction functionality."""

import pytest

pytest.importorskip("presidio_analyzer")
pytest.importorskip("presidio_anonymizer")

from weave.utils import sanitize
from weave.utils.pii_redaction import redact_pii


def test_redact_custom_keys_in_dict() -> None:
    """Test that custom keys added via add_redact_key are redacted in dictionaries.
    
    This is a regression test for https://github.com/wandb/weave/issues/5570
    """
    # Store original keys to restore later
    original_keys = sanitize.get_redact_keys()

    try:
        # Add a custom redaction key
        sanitize.add_redact_key("custom_secret")

        # Test data with the custom key
        data = {
            "email": "test@example.com",
            "custom_secret": "key-12345",
            "normal_field": "normal_value",
        }

        # Redact the data
        redacted = redact_pii(data)

        # The custom_secret value should be redacted
        assert redacted["custom_secret"] == sanitize.REDACTED_VALUE
        
        # The email should be redacted by PII detection
        assert redacted["email"] != "test@example.com"
        
        # Normal field should not be affected
        assert redacted["normal_field"] == "normal_value"

    finally:
        # Restore original keys
        sanitize._REDACT_KEYS = original_keys


def test_redact_custom_keys_nested_dict() -> None:
    """Test that custom keys are redacted in nested dictionaries."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("api_token")
        sanitize.add_redact_key("secret_value")

        data = {
            "user": {
                "name": "John Doe",
                "api_token": "secret-123",
                "config": {
                    "secret_value": "super-secret",
                    "public_value": "visible",
                }
            }
        }

        redacted = redact_pii(data)

        # Check nested redaction
        assert redacted["user"]["api_token"] == sanitize.REDACTED_VALUE
        assert redacted["user"]["config"]["secret_value"] == sanitize.REDACTED_VALUE
        assert redacted["user"]["config"]["public_value"] == "visible"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_custom_keys_in_list() -> None:
    """Test that custom keys are redacted in lists of dictionaries."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("token")

        data = {
            "items": [
                {"description": "first", "token": "token-1"},
                {"description": "second", "token": "token-2"},
            ]
        }

        redacted = redact_pii(data)

        # Check that tokens in list items are redacted
        assert redacted["items"][0]["token"] == sanitize.REDACTED_VALUE
        assert redacted["items"][1]["token"] == sanitize.REDACTED_VALUE
        assert redacted["items"][0]["description"] == "first"
        assert redacted["items"][1]["description"] == "second"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_custom_keys_case_insensitive() -> None:
    """Test that key matching is case-insensitive."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("MySecret")

        data = {
            "mysecret": "value1",
            "MySecret": "value2",
            "MYSECRET": "value3",
        }

        redacted = redact_pii(data)

        # All variations should be redacted
        assert redacted["mysecret"] == sanitize.REDACTED_VALUE
        assert redacted["MySecret"] == sanitize.REDACTED_VALUE
        assert redacted["MYSECRET"] == sanitize.REDACTED_VALUE

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_default_keys_are_redacted() -> None:
    """Test that default keys like api_key are redacted."""
    data = {
        "api_key": "secret-api-key",
        "auth_headers": {"Authorization": "Bearer token"},
        "normal_field": "visible",
    }

    redacted = redact_pii(data)

    # Default keys should be redacted
    assert redacted["api_key"] == sanitize.REDACTED_VALUE
    assert redacted["auth_headers"] == sanitize.REDACTED_VALUE
    assert redacted["normal_field"] == "visible"
