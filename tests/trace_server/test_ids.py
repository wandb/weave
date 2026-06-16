"""Test suite for the home-rolled UUIDv7 implementation."""

import time

from weave.trace_server.ids import generate_id


def test_generate_id_structure() -> None:
    """A generated id is a lowercase-hex 8-4-4-4-12 UUID with the v7 version
    bits (7) and RFC-4122 variant bits (10b) set.
    """
    uuid_str = generate_id()

    # Format: 8-4-4-4-12, all hex.
    parts = uuid_str.split("-")
    assert [len(p) for p in parts] == [8, 4, 4, 4, 12]
    for part in parts:
        int(part, 16)  # raises if not valid hex

    # Lowercase hex only.
    hex_chars = uuid_str.replace("-", "")
    assert hex_chars == hex_chars.lower(), "UUID should use lowercase hex characters"

    # Version 7 (bits 12-15 of byte 6) and variant 10b (bits 0-1 of byte 8).
    uuid_bytes = bytes.fromhex(hex_chars)
    assert (uuid_bytes[6] >> 4) & 0xF == 7
    assert (uuid_bytes[8] >> 6) & 0x3 == 2


def test_generate_id_ordering_and_uniqueness() -> None:
    """The timestamp prefix makes later ids lexicographically greater, and bulk
    generation yields all-distinct ids.
    """
    uuid1 = generate_id()
    time.sleep(0.01)  # 10ms so the millisecond timestamp prefix advances
    uuid2 = generate_id()
    assert uuid2 > uuid1, f"UUID2 ({uuid2}) should be greater than UUID1 ({uuid1})"

    count = 1000
    uuids = {generate_id() for _ in range(count)}
    assert len(uuids) == count, f"Expected {count} unique UUIDs, got {len(uuids)}"
