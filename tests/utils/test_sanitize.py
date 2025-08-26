"""Tests for the sanitize module."""

from weave.utils import sanitize


def test_redact_keys_is_mutable_set() -> None:
    """Test that REDACT_KEYS is a mutable set that can be extended."""
    # Verify REDACT_KEYS is a set
    assert isinstance(sanitize.REDACT_KEYS, set)
    
    # Verify default keys are present
    assert "api_key" in sanitize.REDACT_KEYS
    assert "auth_headers" in sanitize.REDACT_KEYS
    assert "authorization" in sanitize.REDACT_KEYS
    
    # Store original keys to restore later
    original_keys = sanitize.REDACT_KEYS.copy()
    
    try:
        # Test adding new keys
        sanitize.REDACT_KEYS.add("token")
        sanitize.REDACT_KEYS.add("client_id")
        
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
        sanitize.REDACT_KEYS = original_keys


def test_should_redact_case_insensitive() -> None:
    """Test that should_redact is case insensitive."""
    # Test with default keys
    assert sanitize.should_redact("api_key") is True
    assert sanitize.should_redact("Api_Key") is True
    assert sanitize.should_redact("API_KEY") is True
    assert sanitize.should_redact("authorization") is True
    assert sanitize.should_redact("Authorization") is True
    assert sanitize.should_redact("AUTHORIZATION") is True