"""Tests for the sanitize module."""

from weave.utils import sanitize


def test_add_redact_key() -> None:
    """Test the add_redact_key API function."""
    # Store original keys to restore later
    original_keys = sanitize.get_redact_keys()

    try:
        # Add new keys using the API
        sanitize.add_redact_key("token")
        sanitize.add_redact_key("CLIENT_ID")  # Test case normalization

        # Verify keys were added (case normalized to lowercase)
        current_keys = sanitize.get_redact_keys()
        assert "token" in current_keys
        assert "client_id" in current_keys

        # Test that should_redact works with new keys (case insensitive)
        assert sanitize.should_redact("token") is True
        assert sanitize.should_redact("Token") is True
        assert sanitize.should_redact("TOKEN") is True
        assert sanitize.should_redact("client_id") is True
        assert sanitize.should_redact("CLIENT_ID") is True

        # Test that non-redacted keys return False
        assert sanitize.should_redact("random_key") is False

    finally:
        # Restore original keys to avoid affecting other tests
        sanitize._REDACT_KEYS = original_keys


def test_remove_redact_key() -> None:
    """Test the remove_redact_key API function."""
    # Store original keys to restore later
    original_keys = sanitize.get_redact_keys()

    try:
        # Add a test key
        sanitize.add_redact_key("temporary_key")
        assert sanitize.should_redact("temporary_key") is True

        # Remove the key
        sanitize.remove_redact_key("TEMPORARY_KEY")  # Test case normalization
        assert sanitize.should_redact("temporary_key") is False

        # Verify default keys are still present
        assert sanitize.should_redact("api_key") is True
        assert sanitize.should_redact("auth_headers") is True
        assert sanitize.should_redact("authorization") is True

    finally:
        # Restore original keys
        sanitize._REDACT_KEYS = original_keys


def test_get_redact_keys() -> None:
    """Test that get_redact_keys returns a copy."""
    # Get a copy of the keys
    keys_copy = sanitize.get_redact_keys()

    # Verify it contains the default keys
    assert "api_key" in keys_copy
    assert "auth_headers" in keys_copy
    assert "authorization" in keys_copy

    # Verify it's a copy (modifying it doesn't affect the original)
    keys_copy.add("test_key")
    assert "test_key" in keys_copy
    assert "test_key" not in sanitize.get_redact_keys()


def test_should_redact_case_insensitive() -> None:
    """Test that should_redact is case insensitive."""
    # Test with default keys
    assert sanitize.should_redact("api_key") is True
    assert sanitize.should_redact("Api_Key") is True
    assert sanitize.should_redact("API_KEY") is True
    assert sanitize.should_redact("authorization") is True
    assert sanitize.should_redact("Authorization") is True
    assert sanitize.should_redact("AUTHORIZATION") is True
