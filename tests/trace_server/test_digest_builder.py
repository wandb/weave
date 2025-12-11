import re

import pytest

from weave.trace_server.client_server_common.digest_builder import (
    safe_digest,
    table_digest_from_row_digests,
)


def test_safe_digest_ref_stability_external_vs_internal():
    basic_data = {"a": 1, "b": 2}
    basic_data_digest = safe_digest(basic_data)
    object_with_ext_ref = {
        "ref_to_thing": f"weave:///entity/project/object/my_thing:{basic_data_digest}"
    }
    object_with_ext_ref_digest = safe_digest(object_with_ext_ref)

    object_with_int_ref = {
        "ref_to_thing": f"weave-trace-internal:///project_id/object/my_thing:{basic_data_digest}"
    }
    object_with_int_ref_digest = safe_digest(object_with_int_ref)

    assert object_with_ext_ref_digest == object_with_int_ref_digest


def test_bytes_digest_is_deterministic_and_urlsafeish():
    d1 = safe_digest(b"abc")
    d2 = safe_digest(b"abc")
    d3 = safe_digest(b"abcd")

    assert d1 == d2
    assert d1 != d3

    # Our encoding strips '=' padding and replaces '-'/'_' with 'X'/'Y'.
    assert "=" not in d1
    assert "-" not in d1
    assert "_" not in d1
    assert len(d1) == 43

    assert re.fullmatch(r"[A-Za-z0-9]+", d1) is not None


def test_safe_digest_accepts_str_and_is_deterministic():
    # safe_digest should accept strings directly (e.g. source code) and be deterministic.
    s = "hello"
    assert safe_digest(s) == safe_digest(s)
    assert safe_digest(s) != safe_digest("hello2")


def test_table_digest_from_row_digests_is_hex_and_ordered():
    d1 = table_digest_from_row_digests(["row1", "row2"])
    d2 = table_digest_from_row_digests(["row2", "row1"])

    assert d1 != d2
    assert re.fullmatch(r"[0-9a-f]{64}", d1) is not None
    assert re.fullmatch(r"[0-9a-f]{64}", d2) is not None


def test_safe_digest_nested_refs_equivalent():
    payload_digest = safe_digest({"x": 1, "y": 2})

    ext = {
        "a": [
            {"ref": f"weave:///entity/proj/object/Foo:{payload_digest}/attr/bar"},
            "not a ref",
        ],
        "b": {"nested": {"ref2": f"weave:///entity/proj/object/Foo:{payload_digest}"}},
    }
    intr = {
        "a": [
            {
                "ref": f"weave-trace-internal:///proj_id/object/Foo:{payload_digest}/attr/bar"
            },
            "not a ref",
        ],
        "b": {
            "nested": {
                "ref2": f"weave-trace-internal:///proj_id/object/Foo:{payload_digest}"
            }
        },
    }

    assert safe_digest(ext) == safe_digest(intr)


def test_safe_digest_is_stable_to_dict_insertion_order():
    # Same semantic content, different insertion order (including nested dicts).
    v1 = {"a": 1, "b": 2, "c": {"x": 1, "y": 2}}
    v2 = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}

    assert safe_digest(v1) == safe_digest(v2)


def test_safe_digest_recursively_orders_nested_dict_keys():
    # This specifically targets recursive ordering in deeply nested structures,
    # not just top-level insertion order.
    v1 = {
        "outer": {
            "b": {"z": 1, "a": 2},
            "a": [{"k2": 2, "k1": 1}, {"x": 1, "y": 2}],
        }
    }
    v2 = {
        "outer": {
            "a": [{"k1": 1, "k2": 2}, {"y": 2, "x": 1}],
            "b": {"a": 2, "z": 1},
        }
    }
    assert safe_digest(v1) == safe_digest(v2)


def test_safe_digest_raises_on_non_string_dict_keys():
    with pytest.raises(TypeError):
        safe_digest({1: "a"})


def test_safe_digest_is_ref_aware_for_structured_values():
    payload_digest = safe_digest({"x": 1, "y": 2})
    ext = {"ref": f"weave:///entity/proj/object/Foo:{payload_digest}/attr/bar"}
    intr = {
        "ref": f"weave-trace-internal:///proj_id/object/Foo:{payload_digest}/attr/bar"
    }

    assert safe_digest(ext) == safe_digest(intr)


def test_safe_digest_raises_on_sets():
    v = {"s": {3, 1, 2}}
    with pytest.raises(TypeError):
        safe_digest(v)
    with pytest.raises(TypeError):
        safe_digest({1, 2, 3})


def test_safe_digest_does_not_error_on_malformed_refs():
    # Malformed refs should not cause errors; they should remain unchanged (no stabilization).
    malformed_ext = {"r": "weave:///entity/project"}
    malformed_int = {"r": "weave-trace-internal:///project_id"}

    # Should not raise.
    safe_digest(malformed_ext)
    safe_digest(malformed_int)
