import re

from weave.trace_server.client_server_common.digest_builder import (
    bytes_digest,
    ref_aware_json_digest,
    ref_unaware_json_digest,
    str_digest,
    table_digest_from_row_digests,
)


def test_ref_aware_json_digest():
    basic_data = {"a": 1, "b": 2}
    basic_data_digest = ref_aware_json_digest(basic_data)
    object_with_ext_ref = {
        "ref_to_thing": f"weave:///entity/project/object/my_thing:{basic_data_digest}"
    }
    object_with_ext_ref_digest = ref_aware_json_digest(object_with_ext_ref)

    object_with_int_ref = {
        "ref_to_thing": f"weave-trace-internal:///project_id/object/my_thing:{basic_data_digest}"
    }
    object_with_int_ref_digest = ref_aware_json_digest(object_with_int_ref)

    assert object_with_ext_ref_digest == object_with_int_ref_digest


def test_bytes_digest_is_deterministic_and_urlsafeish():
    d1 = bytes_digest(b"abc")
    d2 = bytes_digest(b"abc")
    d3 = bytes_digest(b"abcd")

    assert d1 == d2
    assert d1 != d3

    # Our encoding strips '=' padding and replaces '-'/'_' with 'X'/'Y'.
    assert "=" not in d1
    assert "-" not in d1
    assert "_" not in d1
    assert len(d1) == 43

    assert re.fullmatch(r"[A-Za-z0-9]+", d1) is not None


def test_str_digest_matches_bytes_digest_utf8():
    s = "hello"
    assert str_digest(s) == bytes_digest(s.encode())

    s2 = "∆ unicode"
    assert str_digest(s2) == bytes_digest(s2.encode())


def test_table_digest_from_row_digests_is_hex_and_ordered():
    d1 = table_digest_from_row_digests(["row1", "row2"])
    d2 = table_digest_from_row_digests(["row2", "row1"])

    assert d1 != d2
    assert re.fullmatch(r"[0-9a-f]{64}", d1) is not None
    assert re.fullmatch(r"[0-9a-f]{64}", d2) is not None


def test_ref_aware_json_digest_nested_refs_equivalent():
    payload_digest = ref_aware_json_digest({"x": 1, "y": 2})

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

    assert ref_aware_json_digest(ext) == ref_aware_json_digest(intr)


def test_ref_aware_json_digest_is_stable_to_dict_insertion_order():
    # Same semantic content, different insertion order (including nested dicts).
    v1 = {"a": 1, "b": 2, "c": {"x": 1, "y": 2}}
    v2 = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}

    assert ref_aware_json_digest(v1) == ref_aware_json_digest(v2)


def test_ref_unaware_json_digest_is_stable_to_dict_insertion_order():
    v1 = {"a": 1, "b": 2, "c": {"x": 1, "y": 2}}
    v2 = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}
    assert ref_unaware_json_digest(v1) == ref_unaware_json_digest(v2)


def test_ref_unaware_json_digest_is_ref_unaware_but_ref_aware_json_digest_is_ref_aware():
    payload_digest = ref_unaware_json_digest({"x": 1, "y": 2})
    ext = {"ref": f"weave:///entity/proj/object/Foo:{payload_digest}/attr/bar"}
    intr = {
        "ref": f"weave-trace-internal:///proj_id/object/Foo:{payload_digest}/attr/bar"
    }

    # Ref-unaware digests differ because the owner/entity prefix is different.
    assert ref_unaware_json_digest(ext) != ref_unaware_json_digest(intr)
    # Ref-aware digests are stable to those prefixes.
    assert ref_aware_json_digest(ext) == ref_aware_json_digest(intr)


def test_ref_aware_json_digest_handles_sets_deterministically():
    v1 = {"s": {3, 1, 2}}
    v2 = {"s": {2, 3, 1}}
    assert ref_aware_json_digest(v1) == ref_aware_json_digest(v2)


def test_ref_aware_json_digest_does_not_stabilize_malformed_refs():
    # Malformed refs should not cause errors; they should remain unchanged (no stabilization).
    malformed_ext = {"r": "weave:///entity/project"}
    malformed_int = {"r": "weave-trace-internal:///project_id"}

    assert ref_aware_json_digest(malformed_ext) == ref_unaware_json_digest(
        malformed_ext
    )
    assert ref_aware_json_digest(malformed_int) == ref_unaware_json_digest(
        malformed_int
    )
