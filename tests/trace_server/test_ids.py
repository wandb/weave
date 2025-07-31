"""Test suite for the home-rolled UUIDv7 implementation."""

import time

from weave.trace_server.ids import generate_id


def test_uuid_format():
    """Test that UUIDs are in the correct format."""
    uuid_str = generate_id()

    # Check format (8-4-4-4-12)
    parts = uuid_str.split("-")
    assert len(parts) == 5, f"Expected 5 parts, got {len(parts)}"
    assert len(parts[0]) == 8, f"Part 1 should be 8 chars, got {len(parts[0])}"
    assert len(parts[1]) == 4, f"Part 2 should be 4 chars, got {len(parts[1])}"
    assert len(parts[2]) == 4, f"Part 3 should be 4 chars, got {len(parts[2])}"
    assert len(parts[3]) == 4, f"Part 4 should be 4 chars, got {len(parts[3])}"
    assert len(parts[4]) == 12, f"Part 5 should be 12 chars, got {len(parts[4])}"

    # Check that all parts are hex
    for part in parts:
        int(part, 16)  # Will raise if not valid hex


def test_uuid_version():
    """Test that the version bits are set correctly for UUIDv7."""
    uuid_str = generate_id()

    # Remove hyphens and convert to bytes
    hex_str = uuid_str.replace("-", "")
    uuid_bytes = bytes.fromhex(hex_str)

    # Check version (should be 7, stored in bits 12-15 of byte 6)
    version = (uuid_bytes[6] >> 4) & 0xF
    assert version == 7, f"Expected version 7, got {version}"

    # Check variant (should be 10b, stored in bits 0-1 of byte 8)
    variant = (uuid_bytes[8] >> 6) & 0x3
    assert variant == 2, f"Expected variant 2 (10b), got {variant}"


def test_uuid_timestamp_ordering():
    """Test that UUIDs generated later have higher timestamps."""
    uuid1 = generate_id()
    time.sleep(0.01)  # Sleep for 10ms
    uuid2 = generate_id()

    # Since UUIDv7 has timestamp prefix, uuid2 should be lexicographically greater
    assert uuid2 > uuid1, f"UUID2 ({uuid2}) should be greater than UUID1 ({uuid1})"


def test_uuid_uniqueness():
    """Test that we generate unique UUIDs."""
    uuids = set()
    count = 1000

    for _ in range(count):
        uuid_str = generate_id()
        uuids.add(uuid_str)

    assert len(uuids) == count, f"Expected {count} unique UUIDs, got {len(uuids)}"


def test_uuid_hex_lowercase():
    """Test that UUIDs use lowercase hex characters."""
    uuid_str = generate_id()
    # Remove hyphens for checking
    hex_chars = uuid_str.replace("-", "")
    assert hex_chars == hex_chars.lower(), "UUID should use lowercase hex characters"
