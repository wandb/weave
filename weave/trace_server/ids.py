# Note: Home-rolled UUIDv7 implementation to avoid dependency on uuid_utils
# which has issues on Windows. UUIDv7 has a timestamp prefix, so that the IDs,
# while random, are sortable by time. See RFC9562 https://www.rfc-editor.org/rfc/rfc9562
# Inspired by https://antonz.org/uuidv7/#python
import os
import time


def _generate_uuidv7_bytes() -> bytes:
    """Generate UUIDv7 bytes according to RFC9562."""
    # Generate 16 random bytes
    value = bytearray(os.urandom(16))

    # Current timestamp in milliseconds
    timestamp = int(time.time() * 1000)

    # Place timestamp in first 48 bits (6 bytes)
    value[0] = (timestamp >> 40) & 0xFF
    value[1] = (timestamp >> 32) & 0xFF
    value[2] = (timestamp >> 24) & 0xFF
    value[3] = (timestamp >> 16) & 0xFF
    value[4] = (timestamp >> 8) & 0xFF
    value[5] = timestamp & 0xFF

    # Set version (7) in bits 12-15 of byte 6
    value[6] = (value[6] & 0x0F) | 0x70

    # Set variant (10) in bits 0-1 of byte 8
    value[8] = (value[8] & 0x3F) | 0x80

    return bytes(value)


def generate_id() -> str:
    """Should be used to generate IDs for trace calls.
    We use UUIDv7, which has a timestamp prefix, so that the IDs, while random,
    are sortable by time. See RFC9562 https://www.rfc-editor.org/rfc/rfc9562

    Random space is 2^74, which is less than 2^122 (UUIDv4), but still plenty
    for our use case.
    """
    uuid_bytes = _generate_uuidv7_bytes()

    # Convert to standard UUID string format: 8-4-4-4-12
    hex_str = "".join(f"{byte:02x}" for byte in uuid_bytes)
    return f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"
