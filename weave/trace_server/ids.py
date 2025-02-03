# Note: `uuid_utils` is a pure UUID drop in replacement that leverages Rust's
# UUID library for performance. We may want to write our own UUIDv7
# implementation to support python < 3.8. However, Weave already requires >=3.9,
# so we can just use the library.
import uuid_utils as uuid


def generate_id() -> str:
    """Should be used to generate IDs for trace calls.
    We use UUIDv7, which has a timestamp prefix, so that the IDs, while random,
    are sortable by time. See RFC9562 https://www.rfc-editor.org/rfc/rfc9562

    Random space is 2^74, which is less than 2^122 (UUIDv4), but still plenty
    for our use case.
    """
    return str(uuid.uuid7())
