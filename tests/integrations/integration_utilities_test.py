import pytest

from weave.integrations.integration_utilities import (
    _make_string_of_length,
    _truncated_str,
    truncate_op_name,
)
from weave.trace_server.constants import MAX_OP_NAME_LENGTH

NON_HASH_LIMIT = 5


def test_truncate_op_name_less_than_limit() -> None:
    name = _make_string_of_length(MAX_OP_NAME_LENGTH - 1)
    trunc = truncate_op_name(name)
    assert trunc == name


def test_truncate_op_name_at_limit() -> None:
    name = _make_string_of_length(MAX_OP_NAME_LENGTH)
    trunc = truncate_op_name(name)
    assert trunc == name


def test_truncate_op_name_too_short_for_hash() -> None:
    # Remove 1 character for a range of tail lengths:
    chars_to_remove = 1
    for tail_len in range(NON_HASH_LIMIT + 1):
        if tail_len <= chars_to_remove:
            with pytest.raises(ValueError):
                name, trunc = _truncated_str(
                    tail_len, MAX_OP_NAME_LENGTH + chars_to_remove
                )
        else:
            name, trunc = _truncated_str(tail_len, MAX_OP_NAME_LENGTH + chars_to_remove)
            assert trunc == name[:MAX_OP_NAME_LENGTH]

    name, trunc = _truncated_str(NON_HASH_LIMIT + 1, MAX_OP_NAME_LENGTH + 1)
    assert (
        trunc
        == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.a_0_a"
    )

    # Remove a range of character for a fixed tail length:
    tail_len = NON_HASH_LIMIT
    for chars_to_remove in range(0, tail_len + 1):
        if tail_len <= chars_to_remove:
            with pytest.raises(ValueError):
                name, trunc = _truncated_str(
                    tail_len, MAX_OP_NAME_LENGTH + chars_to_remove
                )
        else:
            name, trunc = _truncated_str(tail_len, MAX_OP_NAME_LENGTH + chars_to_remove)
            assert trunc == name[:MAX_OP_NAME_LENGTH]


def test_truncate_op_name_with_digest() -> None:
    name = _make_string_of_length(MAX_OP_NAME_LENGTH + 1)
    trunc = truncate_op_name(name)
    assert (
        trunc
        == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_b325_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    name = _make_string_of_length(MAX_OP_NAME_LENGTH + 10)
    trunc = truncate_op_name(name)
    assert (
        trunc
        == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_55b6_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
