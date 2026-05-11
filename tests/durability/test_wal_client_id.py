"""Tests for the SHA-256 client identity hash."""

from __future__ import annotations

from weave.durability.wal_client_id import compute_client_id


class TestComputeClientId:
    def test_deterministic(self):
        """Same API key = same client ID."""
        assert compute_client_id("wk-abc123") == compute_client_id("wk-abc123")

    def test_different_keys_produce_different_ids(self):
        assert compute_client_id("wk-abc123") != compute_client_id("wk-xyz789")

    def test_id_is_hex_string(self):
        client_id = compute_client_id("wk-abc123")
        assert all(c in "0123456789abcdef" for c in client_id)

    def test_id_length(self):
        # SHA-256 hex digest is always 64 chars
        assert len(compute_client_id("wk-abc123")) == 64
