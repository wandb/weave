"""Tests for PII redaction functionality."""

import dataclasses
import os
from unittest import mock

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
                },
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


def test_redact_dataclass_fields() -> None:
    """Test that dataclass fields are redacted when their names are in the redact set."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("api_key")

        @dataclasses.dataclass
        class UserConfig:
            api_key: str
            username: str
            api_token: str

        config = UserConfig(
            api_key="secret-key-123",
            username="testuser",
            api_token="token-456",
        )

        redacted = redact_pii(config)

        # The api_key field should be redacted
        assert redacted.api_key == sanitize.REDACTED_VALUE
        # api_token should not be redacted (not in redact set)
        assert redacted.api_token == "token-456"
        # username should not be redacted
        assert redacted.username == "testuser"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_dataclass_nested() -> None:
    """Test that nested dataclasses are redacted correctly."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("secret")

        @dataclasses.dataclass
        class InnerConfig:
            secret: str
            public: str

        @dataclasses.dataclass
        class OuterConfig:
            inner: InnerConfig
            name: str

        config = OuterConfig(
            inner=InnerConfig(secret="hidden", public="visible"),
            name="test",
        )

        redacted = redact_pii(config)

        # Nested dataclass field should be redacted
        assert redacted.inner.secret == sanitize.REDACTED_VALUE
        assert redacted.inner.public == "visible"
        assert redacted.name == "test"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_dataclass_in_list() -> None:
    """Test that dataclasses in lists are redacted."""
    original_keys = sanitize.get_redact_keys()

    try:
        sanitize.add_redact_key("api_key")

        @dataclasses.dataclass
        class Credential:
            api_key: str
            username: str

        credentials = [
            Credential(api_key="key1", username="user1"),
            Credential(api_key="key2", username="user2"),
        ]

        redacted = redact_pii(credentials)

        # All dataclass instances in the list should have api_key redacted
        assert redacted[0].api_key == sanitize.REDACTED_VALUE
        assert redacted[0].username == "user1"
        assert redacted[1].api_key == sanitize.REDACTED_VALUE
        assert redacted[1].username == "user2"

    finally:
        sanitize._REDACT_KEYS = original_keys


def test_redact_pii_exclude_fields() -> None:
    """Test that redact_pii_exclude_fields excludes entities from redaction."""
    with mock.patch.dict(
        os.environ, {"WEAVE_REDACT_PII_EXCLUDE_FIELDS": "EMAIL_ADDRESS"}, clear=True
    ):
        data = {"email": "test@example.com", "name": "John Doe"}
        redacted = redact_pii(data)

        assert redacted["email"] == "test@example.com"
        assert "John Doe" not in redacted["name"]
