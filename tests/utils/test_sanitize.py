"""Tests for the sanitize module."""

from weave.utils import sanitize


def test_redact_key_api_add_remove_and_case_insensitivity() -> None:
    """add/remove_redact_key normalize case, should_redact is case-insensitive, and defaults persist."""
    original_keys = sanitize.get_redact_keys()
    try:
        # Default keys are redacted regardless of case.
        for default in ("api_key", "auth_headers", "authorization"):
            assert sanitize.should_redact(default) is True
        assert sanitize.should_redact("Api_Key") is True
        assert sanitize.should_redact("API_KEY") is True
        assert sanitize.should_redact("Authorization") is True
        assert sanitize.should_redact("AUTHORIZATION") is True

        # add_redact_key normalizes to lowercase and is case-insensitive on lookup.
        sanitize.add_redact_key("token")
        sanitize.add_redact_key("CLIENT_ID")
        current_keys = sanitize.get_redact_keys()
        assert "token" in current_keys
        assert "client_id" in current_keys
        for variant in ("token", "Token", "TOKEN", "client_id", "CLIENT_ID"):
            assert sanitize.should_redact(variant) is True
        assert sanitize.should_redact("random_key") is False

        # remove_redact_key normalizes case and leaves defaults intact.
        sanitize.remove_redact_key("TOKEN")
        assert sanitize.should_redact("token") is False
        assert sanitize.should_redact("api_key") is True
    finally:
        sanitize._REDACT_KEYS = original_keys


def test_get_redact_keys_returns_independent_copy() -> None:
    """get_redact_keys returns a fresh set; mutating it does not affect the source of truth."""
    keys_copy = sanitize.get_redact_keys()
    assert "api_key" in keys_copy
    assert "auth_headers" in keys_copy
    assert "authorization" in keys_copy

    keys_copy.add("test_key")
    assert "test_key" in keys_copy
    assert "test_key" not in sanitize.get_redact_keys()
