"""Tests for client-side digest correctness.

Verifies that digests computed on the client (fast path) match those computed
on the server (fallback path) for various object and table shapes.
"""

from __future__ import annotations

import logging

import pytest

import weave
from weave.trace.refs import ObjectRef, OpRef, TableRef
from weave.trace.serialization.serialize import to_json
from weave.trace.settings import UserSettings, parse_and_apply_settings
from weave.trace.weave_client import WeaveClient
from weave.trace_server.errors import DigestMismatchError
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
    client._invalidate_project_cache()
    ref = weave.publish(obj, name=name)
    client._flush()
    return ref.digest


def _make_ref(kind: str, entity: str, project: str) -> ObjectRef | OpRef | TableRef:
    if kind == "object":
        return ObjectRef(entity, project, "thing", "abc123")
    if kind == "op":
        return OpRef(entity, project, "my_op", "def456")
    if kind == "table":
        return TableRef(entity, project, "tab123")
    raise ValueError(f"Unknown ref kind: {kind}")


def _expected_internal_ref_uri(kind: str, internal_project_id: str) -> str:
    if kind == "object":
        return f"weave-trace-internal:///{internal_project_id}/object/thing:abc123"
    if kind == "op":
        return f"weave-trace-internal:///{internal_project_id}/op/my_op:def456"
    if kind == "table":
        return f"weave-trace-internal:///{internal_project_id}/table/tab123"
    raise ValueError(f"Unknown ref kind: {kind}")


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


@pytest.mark.parametrize("kind", ["object", "op", "table"])
def test_cross_project_ref_matches_string_ref_serialization(
    client: WeaveClient,
    kind: str,
) -> None:
    """Each cross-project ref kind should match its URI string form."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))

    current_internal_project_id = client._internal_project_id
    assert current_internal_project_id is not None

    other_project = "other-project"
    other_ext_project_id = f"{client.entity}/{other_project}"
    other_internal_project_id = client._resolve_ext_to_int_project_id(
        other_ext_project_id
    )
    assert other_internal_project_id is not None

    ref = _make_ref(kind, client.entity, other_project)
    expected_uri = _expected_internal_ref_uri(kind, other_internal_project_id)

    # Each simple case covers both the typed ref object and its raw URI string
    # form so we catch divergence between those two serialization entry points.
    assert (
        to_json(
            ref,
            client._project_id(),
            client,
            internal_project_id=current_internal_project_id,
        )
        == expected_uri
    )
    assert (
        to_json(
            ref.uri(),
            client._project_id(),
            client,
            internal_project_id=current_internal_project_id,
        )
        == expected_uri
    )


def test_nested_cross_project_refs_preserve_individual_projects(
    client: WeaveClient,
) -> None:
    """Nested payloads should preserve per-ref project mapping during recursion."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))

    current_internal_project_id = client._internal_project_id
    assert current_internal_project_id is not None

    other_project = "other-project"
    other_ext_project_id = f"{client.entity}/{other_project}"
    other_internal_project_id = client._resolve_ext_to_int_project_id(
        other_ext_project_id
    )
    assert other_internal_project_id is not None

    same_project_ref = ObjectRef(client.entity, client.project, "local", "ghi789")
    obj_ref = ObjectRef(client.entity, other_project, "thing", "abc123")
    op_ref = OpRef(client.entity, other_project, "my_op", "def456")
    table_ref = TableRef(client.entity, other_project, "tab123")

    expected_same_project_uri = (
        f"weave-trace-internal:///{current_internal_project_id}/object/local:ghi789"
    )
    expected_obj_uri = _expected_internal_ref_uri("object", other_internal_project_id)
    expected_op_uri = _expected_internal_ref_uri("op", other_internal_project_id)
    expected_table_uri = _expected_internal_ref_uri("table", other_internal_project_id)

    # Cross-project refs are often buried in nested containers alongside
    # same-project refs. The serializer needs to recurse without losing which
    # project each individual ref belongs to.
    assert to_json(
        {
            "typed": [same_project_ref, obj_ref],
            "mixed": {
                "op_uri": op_ref.uri(),
                "table": table_ref,
            },
            "tuple_like": (obj_ref.uri(), same_project_ref, table_ref.uri()),
        },
        client._project_id(),
        client,
        internal_project_id=current_internal_project_id,
    ) == {
        "typed": [expected_same_project_uri, expected_obj_uri],
        "mixed": {
            "op_uri": expected_op_uri,
            "table": expected_table_uri,
        },
        "tuple_like": [
            expected_obj_uri,
            expected_same_project_uri,
            expected_table_uri,
        ],
    }


# ---------------------------------------------------------------------------
# Round-trip: publish via fast path, read back, verify data
# ---------------------------------------------------------------------------


def test_object_round_trip_fast_path(client: WeaveClient):
    """Object published via fast path can be read back with correct data."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))
    client._invalidate_project_cache()

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
    client._invalidate_project_cache()

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


def test_typed_cross_project_ref_round_trip_fast_path(client: WeaveClient):
    """A typed cross-project ref should keep its original project on read-back."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))

    original_project = client.project

    client.project = "other-project"
    inner_ref = client._save_object({"msg": "hi"}, "inner-cross-project")
    client._flush()

    client.project = original_project
    outer_ref = client._save_object({"ref": inner_ref}, "outer-with-typed-ref")
    client._flush()

    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client._project_id(),
            object_id="outer-with-typed-ref",
            digest=outer_ref.digest,
        )
    )

    assert read_res.obj.val["ref"] == inner_ref.uri()


# ---------------------------------------------------------------------------
# Server-side validation: expected_digest is checked
# ---------------------------------------------------------------------------


def test_server_rejects_wrong_expected_digest(client: WeaveClient):
    """Server raises DigestMismatchError when expected_digest doesn't match."""
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


@pytest.mark.disable_logging_error_check
def test_digest_mismatch_warning_disables_fast_path_for_session(
    client: WeaveClient, monkeypatch, caplog
) -> None:
    """A fast-path digest mismatch should warn and force later saves to fallback."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))
    client._invalidate_project_cache()

    original_obj_create = client.server.server.obj_create
    seen_expected_digests: list[str | None] = []
    injected_mismatch = False

    def obj_create_with_mismatch(req: tsi.ObjCreateReq):
        nonlocal injected_mismatch
        seen_expected_digests.append(req.obj.expected_digest)
        if not injected_mismatch and req.obj.expected_digest is not None:
            injected_mismatch = True
            raise DigestMismatchError("client digest mismatch")
        return original_obj_create(req)

    monkeypatch.setattr(client.server.server, "obj_create", obj_create_with_mismatch)
    caplog.set_level(logging.WARNING, logger="weave.trace.weave_client")

    # The first save uses the fast path and returns a ref immediately even
    # though the server later rejects the expected_digest. The callback should
    # warn and disable the fast path so later saves fall back safely.
    first_ref = weave.publish({"first": True}, name="digest-mismatch-first")
    client._flush()

    assert seen_expected_digests == [first_ref.digest]
    assert client._client_side_digests_disabled_for_session is True
    assert client._internal_project_id is None
    assert any(
        "disabling fast path for this session" in record.getMessage()
        and first_ref.uri() in record.getMessage()
        for record in caplog.records
        if record.name == "weave.trace.weave_client"
    )

    weave.publish({"second": True}, name="digest-mismatch-second")
    client._flush()

    assert seen_expected_digests == [first_ref.digest, None]


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
    client._invalidate_project_cache()
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
