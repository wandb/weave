"""Tests for client-side digest correctness.

Verifies that digests computed on the client (fast path) match those computed
on the server (fallback path) for various object and table shapes.
"""

from __future__ import annotations

import pytest

import weave
from weave.trace.settings import UserSettings, parse_and_apply_settings
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset settings to defaults after each test to avoid leaking state."""
    yield
    parse_and_apply_settings(UserSettings())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _publish_with_digests(
    client: WeaveClient,
    obj: object,
    name: str,
    *,
    enable: bool,
) -> str:
    """Publish *obj* under *name* and return the digest string.

    Toggles client-side digests on/off via settings before publishing.
    """
    parse_and_apply_settings(UserSettings(enable_client_side_digests=enable))
    # Re-resolve the internal project ID so the toggle takes effect.
    client._cached_internal_project_id_for = None
    ref = weave.publish(obj, name=name)
    client._flush()
    return ref.digest


# ---------------------------------------------------------------------------
# Cross-path: same data → same digest regardless of path
# ---------------------------------------------------------------------------


def test_object_digest_matches_across_paths(client: WeaveClient):
    """Publishing the same object via fast and fallback paths gives the same digest."""
    obj = {"model": "gpt-4", "temperature": 0.7, "tags": ["a", "b"]}

    digest_fast = _publish_with_digests(client, obj, "obj_fast", enable=True)
    digest_fallback = _publish_with_digests(client, obj, "obj_fallback", enable=False)

    assert digest_fast == digest_fallback


def test_dataset_digest_matches_across_paths(client: WeaveClient):
    """Publishing the same Dataset via fast and fallback paths gives the same digest."""
    rows = [{"x": i, "y": str(i)} for i in range(10)]

    ds_fast = weave.Dataset(name="bench_ds", rows=rows)
    digest_fast = _publish_with_digests(client, ds_fast, "ds_fast", enable=True)

    ds_fallback = weave.Dataset(name="bench_ds", rows=rows)
    digest_fallback = _publish_with_digests(
        client, ds_fallback, "ds_fallback", enable=False
    )

    assert digest_fast == digest_fallback


def test_nested_object_digest_matches_across_paths(client: WeaveClient):
    """Nested dicts produce the same digest regardless of path."""
    obj = {
        "config": {"a": 1, "b": [2, 3]},
        "metadata": {"nested": {"deep": True}},
    }

    digest_fast = _publish_with_digests(client, obj, "nested_fast", enable=True)
    digest_fallback = _publish_with_digests(
        client, obj, "nested_fallback", enable=False
    )

    assert digest_fast == digest_fallback


# ---------------------------------------------------------------------------
# Round-trip: publish via fast path, read back, verify data
# ---------------------------------------------------------------------------


def test_object_round_trip_fast_path(client: WeaveClient):
    """Object published via fast path can be read back with correct data."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))
    client._cached_internal_project_id_for = None

    obj = {"key": "value", "number": 42, "list": [1, 2, 3]}
    ref = weave.publish(obj, name="round_trip_obj")
    client._flush()

    got = ref.get()
    assert got["key"] == "value"
    assert got["number"] == 42
    assert got["list"] == [1, 2, 3]


def test_dataset_round_trip_fast_path(client: WeaveClient):
    """Dataset published via fast path can be read back with correct rows."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))
    client._cached_internal_project_id_for = None

    rows = [{"a": i, "b": i * 2} for i in range(5)]
    ds = weave.Dataset(name="round_trip_ds", rows=rows)
    ref = weave.publish(ds)
    client._flush()

    got = ref.get()
    got_rows = list(got.rows)
    assert len(got_rows) == 5
    for i, row in enumerate(got_rows):
        assert row["a"] == i
        assert row["b"] == i * 2


# ---------------------------------------------------------------------------
# Server-side validation: expected_digest is checked
# ---------------------------------------------------------------------------


def test_server_rejects_wrong_expected_digest(client: WeaveClient):
    """Server raises DigestMismatchError when expected_digest doesn't match."""
    from weave.trace_server.errors import DigestMismatchError

    req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(
            project_id=client._project_id(),
            object_id="bad_digest_obj",
            val={"hello": "world"},
            expected_digest="definitely_wrong_digest",
        )
    )

    try:
        client.server.obj_create(req)
        raise AssertionError("Expected DigestMismatchError")
    except (DigestMismatchError, Exception) as e:
        # When going through HTTP, this comes back as an HTTP error (409)
        # When going through direct server, it's DigestMismatchError
        assert (
            "digest" in str(e).lower()
            or "409" in str(e)
            or "mismatch" in str(e).lower()
        )


def test_server_rejects_wrong_table_expected_digest(client: WeaveClient):
    """Server raises DigestMismatchError for table with wrong expected_digest."""
    from weave.trace_server.errors import DigestMismatchError

    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client._project_id(),
            rows=[{"a": 1}, {"a": 2}],
            expected_digest="definitely_wrong_digest",
        )
    )

    try:
        client.server.table_create(req)
        raise AssertionError("Expected DigestMismatchError")
    except (DigestMismatchError, Exception) as e:
        assert (
            "digest" in str(e).lower()
            or "409" in str(e)
            or "mismatch" in str(e).lower()
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_dict_digest_matches(client: WeaveClient):
    """Empty dict produces the same digest on both paths."""
    obj: dict = {}

    digest_fast = _publish_with_digests(client, obj, "empty_fast", enable=True)
    digest_fallback = _publish_with_digests(client, obj, "empty_fallback", enable=False)

    assert digest_fast == digest_fallback


def test_unicode_content_digest_matches(client: WeaveClient):
    """Unicode strings produce the same digest on both paths."""
    obj = {
        "emoji": "\U0001f680\U0001f30d",
        "cjk": "\u4f60\u597d\u4e16\u754c",
        "accent": "\u00e9\u00e0\u00fc",
    }

    digest_fast = _publish_with_digests(client, obj, "unicode_fast", enable=True)
    digest_fallback = _publish_with_digests(
        client, obj, "unicode_fallback", enable=False
    )

    assert digest_fast == digest_fallback


def test_large_dataset_digest_matches(client: WeaveClient):
    """Larger dataset (100 rows) produces matching digests."""
    rows = [
        {"idx": i, "val": f"row_{i}", "data": list(range(i % 10))} for i in range(100)
    ]

    ds_fast = weave.Dataset(name="bench_large_ds", rows=rows)
    digest_fast = _publish_with_digests(client, ds_fast, "large_fast", enable=True)

    ds_fallback = weave.Dataset(name="bench_large_ds", rows=rows)
    digest_fallback = _publish_with_digests(
        client, ds_fallback, "large_fallback", enable=False
    )

    assert digest_fast == digest_fallback


def test_object_with_ref_digest_matches(client: WeaveClient):
    """Object containing a ref to another object gets the same digest on both paths."""
    # First publish a nested object (use fallback to avoid path dependency)
    parse_and_apply_settings(UserSettings(enable_client_side_digests=False))
    client._cached_internal_project_id_for = None
    inner = {"inner_key": "inner_value"}
    inner_ref = weave.publish(inner, name="inner_obj")
    client._flush()

    # Now publish an object that references it, via both paths
    outer = {"ref": inner_ref.uri(), "extra": "data"}

    digest_fast = _publish_with_digests(client, outer, "outer_fast", enable=True)
    digest_fallback = _publish_with_digests(
        client, outer, "outer_fallback", enable=False
    )

    assert digest_fast == digest_fallback
