"""Tests for client-side digest correctness.

Verifies that digests computed on the client (fast path) match those computed
on the server (fallback path) for various object and table shapes.
"""

from __future__ import annotations

import logging
import threading

import pytest
from PIL import Image

import weave
from weave.shared.digest import compute_row_digest, compute_table_digest
from weave.trace.refs import ObjectRef, OpRef, TableRef
from weave.trace.serialization.serialize import to_json
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
    should_enable_client_side_digests,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import DigestMismatchError


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset settings to defaults after each test to avoid leaking state."""
    yield
    parse_and_apply_settings(UserSettings())


@pytest.fixture
def fast_path(client: WeaveClient):
    """Enable the client-side digest fast path for a test."""
    _enable_fast_path(client)
    yield
    _disable_fast_path(client)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enable_fast_path(client: WeaveClient) -> None:
    """Enable client-side digests on an already-created client."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))
    client._invalidate_project_cache()


def _disable_fast_path(client: WeaveClient) -> None:
    """Disable client-side digests on an already-created client."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=False))
    client._invalidate_project_cache()


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
    if enable:
        _enable_fast_path(client)
    else:
        _disable_fast_path(client)
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
    fast_path: None,
    kind: str,
) -> None:
    """Each cross-project ref kind should match its URI string form."""
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
    fast_path: None,
) -> None:
    """Nested payloads should preserve per-ref project mapping during recursion."""
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


def test_object_round_trip_fast_path(client: WeaveClient, fast_path: None):
    """Object published via fast path can be read back with correct data."""
    obj = {"key": "value", "number": 42, "list": [1, 2, 3]}
    ref = weave.publish(obj, name="round_trip_obj")
    client._flush()

    got = ref.get()
    assert got["key"] == "value"
    assert got["number"] == 42
    assert got["list"] == [1, 2, 3]


def test_dataset_round_trip_fast_path(client: WeaveClient, fast_path: None):
    """Dataset published via fast path can be read back with correct rows."""
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


def test_typed_cross_project_ref_round_trip_fast_path(
    client: WeaveClient, fast_path: None
):
    """A typed cross-project ref should keep its original project on read-back."""
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

    with pytest.raises(Exception, match=r"(?i)digest|409|mismatch"):
        client.server.obj_create(req)


def test_server_rejects_wrong_table_expected_digest(client: WeaveClient):
    """Server raises DigestMismatchError for table with wrong expected_digest."""
    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client._project_id(),
            rows=[{"a": 1}, {"a": 2}],
            expected_digest="definitely_wrong_digest",
        )
    )

    with pytest.raises(Exception, match=r"(?i)digest|409|mismatch"):
        client.server.table_create(req)


@pytest.mark.disable_logging_error_check
def test_digest_mismatch_warning_disables_fast_path_for_session(
    client: WeaveClient, fast_path: None, monkeypatch, caplog
) -> None:
    """A fast-path digest mismatch should warn and force later saves to fallback."""
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
    assert client._client_side_digests_disabled_event.is_set()
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
    _disable_fast_path(client)
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


def test_custom_weave_type_round_trip_fast_path(client: WeaveClient, fast_path: None):
    """A CustomWeaveType (PIL Image) published via fast path can be read back."""
    img = Image.new("RGB", (32, 32), color=(255, 0, 0))
    ref = weave.publish(img, name="fast_path_image")
    client._flush()

    got = ref.get()
    assert isinstance(got, Image.Image)
    assert got.size == (32, 32)
    assert got.getpixel((0, 0)) == (255, 0, 0)


def test_custom_weave_type_digest_matches_across_paths(client: WeaveClient):
    """A CustomWeaveType (PIL Image) produces the same digest on both paths."""
    img_fast = Image.new("RGB", (16, 16), color=(0, 128, 255))
    digest_fast = _publish_with_digests(client, img_fast, "img_fast", enable=True)

    img_fallback = Image.new("RGB", (16, 16), color=(0, 128, 255))
    digest_fallback = _publish_with_digests(
        client, img_fallback, "img_fallback", enable=False
    )

    assert digest_fast == digest_fallback


# ---------------------------------------------------------------------------
# Serialization: internal_project_id ref conversion
# ---------------------------------------------------------------------------


def test_to_json_converts_same_project_ref_to_internal_uri(
    client: WeaveClient,
    fast_path: None,
) -> None:
    """to_json with internal_project_id converts same-project ObjectRef to internal URI.

    Requirement: When client-side digests are enabled, refs in the same project
    must be serialized using internal URIs so the server can validate them.
    """
    internal_id = client._internal_project_id
    assert internal_id is not None

    ref = ObjectRef(client.entity, client.project, "myobj", "abc123")
    result = to_json(ref, client._project_id(), client, internal_project_id=internal_id)

    assert result == f"weave-trace-internal:///{internal_id}/object/myobj:abc123"


def test_to_json_without_internal_id_keeps_external_uri(
    client: WeaveClient,
) -> None:
    """to_json without internal_project_id preserves external weave:/// URIs.

    Requirement: The fallback path must not convert refs to internal format.
    """
    ref = ObjectRef(client.entity, client.project, "myobj", "abc123")
    result = to_json(ref, client._project_id(), client)

    assert result == f"weave:///{client.entity}/{client.project}/object/myobj:abc123"


def test_to_json_converts_ref_uri_strings_with_internal_id(
    client: WeaveClient,
    fast_path: None,
) -> None:
    """Raw weave:/// URI strings are also converted when internal_project_id is set.

    Requirement: Both typed Ref objects and raw URI strings must be converted
    consistently, since either may appear in serialized payloads.
    """
    internal_id = client._internal_project_id
    assert internal_id is not None

    uri_string = f"weave:///{client.entity}/{client.project}/object/myobj:abc123"
    result = to_json(
        uri_string, client._project_id(), client, internal_project_id=internal_id
    )

    assert result == f"weave-trace-internal:///{internal_id}/object/myobj:abc123"


# ---------------------------------------------------------------------------
# Settings toggle: fast vs fallback path selection
# ---------------------------------------------------------------------------


def test_fast_path_sends_expected_digest(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    """When client-side digests are enabled, obj_create receives expected_digest.

    Requirement: The fast path must send the client-computed digest to the
    server for validation. This is the core contract of the feature.
    """
    captured_digests: list[str | None] = []
    original_obj_create = client.server.server.obj_create

    def capturing_obj_create(req: tsi.ObjCreateReq):
        captured_digests.append(req.obj.expected_digest)
        return original_obj_create(req)

    monkeypatch.setattr(client.server.server, "obj_create", capturing_obj_create)

    weave.publish({"test": "fast_path"}, name="fast-path-test")
    client._flush()

    assert len(captured_digests) == 1
    assert captured_digests[0] is not None


def test_fallback_path_sends_no_expected_digest(
    client: WeaveClient, monkeypatch
) -> None:
    """When client-side digests are disabled, obj_create receives no expected_digest.

    Requirement: The fallback path must not send expected_digest, deferring
    digest computation entirely to the server.
    """
    _disable_fast_path(client)

    captured_digests: list[str | None] = []
    original_obj_create = client.server.server.obj_create

    def capturing_obj_create(req: tsi.ObjCreateReq):
        captured_digests.append(req.obj.expected_digest)
        return original_obj_create(req)

    monkeypatch.setattr(client.server.server, "obj_create", capturing_obj_create)

    weave.publish({"test": "fallback_path"}, name="fallback-path-test")
    client._flush()

    assert len(captured_digests) == 1
    assert captured_digests[0] is None


def test_env_var_enables_client_side_digests(monkeypatch) -> None:
    """WEAVE_ENABLE_CLIENT_SIDE_DIGESTS env var toggles the setting.

    Requirement: Users can enable client-side digests without code changes
    by setting an environment variable.
    """
    # Reset to defaults first
    parse_and_apply_settings(UserSettings())

    monkeypatch.setenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", "true")
    assert should_enable_client_side_digests() is True

    monkeypatch.setenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", "false")
    assert should_enable_client_side_digests() is False

    monkeypatch.delenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", raising=False)


# ---------------------------------------------------------------------------
# Table fast path: row_digests tracking
# ---------------------------------------------------------------------------


def test_table_fast_path_produces_valid_row_digests(
    client: WeaveClient, fast_path: None
) -> None:
    """Table created via fast path returns row_digests from the server.

    Requirement: The server must return row_digests that match what
    compute_row_digest produces for each row, ensuring the client and
    server agree on per-row identity.
    """
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}]
    row_digests = [compute_row_digest(r) for r in rows]
    table_digest = compute_table_digest(row_digests)

    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client._project_id(),
            rows=rows,
            expected_digest=table_digest,
        )
    )
    res = client.server.table_create(req)

    assert res.digest == table_digest
    assert res.row_digests == row_digests


def test_table_row_digests_match_across_paths(client: WeaveClient) -> None:
    """Table row digests from fast and fallback paths must agree.

    Requirement: Row digests are used to identify individual rows. They
    must be identical regardless of which path computed them.
    """
    rows = [{"x": i, "y": str(i)} for i in range(5)]

    # Fast path: compute client-side
    fast_row_digests = [compute_row_digest(r) for r in rows]
    fast_table_digest = compute_table_digest(fast_row_digests)

    # Fallback path: let server compute
    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client._project_id(),
            rows=rows,
        )
    )
    res = client.server.table_create(req)

    assert res.row_digests == fast_row_digests
    assert res.digest == fast_table_digest


# ---------------------------------------------------------------------------
# Op digest consistency
# ---------------------------------------------------------------------------


def test_op_digest_matches_across_paths(client: WeaveClient) -> None:
    """An op published via fast and fallback paths produces the same digest.

    Requirement: @weave.op decorated functions are a key user-facing type.
    Their digests must be consistent across paths just like plain objects.
    """

    @weave.op
    def my_test_op(x: int) -> int:
        return x + 1

    digest_fast = _publish_with_digests(client, my_test_op, "op_fast", enable=True)
    digest_fallback = _publish_with_digests(
        client, my_test_op, "op_fallback", enable=False
    )

    assert digest_fast == digest_fallback


# ---------------------------------------------------------------------------
# Inflight save tracking: fast-path refs are immediately usable
# ---------------------------------------------------------------------------


def test_fast_path_ref_get_succeeds_without_explicit_flush(
    client: WeaveClient,
    fast_path: None,
) -> None:
    """A fast-path ref can be .get()'d after flush.

    Requirement: The fast path returns a ref with the digest immediately.
    After flushing, the data is available on the server.
    """
    obj = {"immediate": "access", "count": 99}
    ref = weave.publish(obj, name="fast-path-get-test")

    got = ref.get()
    assert got["immediate"] == "access"
    assert got["count"] == 99


# ---------------------------------------------------------------------------
# Server validation: correct expected_digest is accepted
# ---------------------------------------------------------------------------


def test_server_accepts_correct_expected_digest(client: WeaveClient) -> None:
    """Server accepts obj_create when expected_digest matches.

    Requirement: The happy path — when the client computes the correct
    digest, the server should accept it without error.
    """
    from weave.shared.digest import compute_object_digest

    val = {"server": "accepts", "this": True}
    digest = compute_object_digest(val)

    req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(
            project_id=client._project_id(),
            object_id="correct_digest_obj",
            val=val,
            expected_digest=digest,
        )
    )

    # Should not raise
    res = client.server.obj_create(req)
    assert res.digest == digest


def test_server_accepts_correct_table_expected_digest(client: WeaveClient) -> None:
    """Server accepts table_create when expected_digest matches.

    Requirement: Same as above but for tables — the computed table digest
    must be accepted by the server.
    """
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    row_digests = [compute_row_digest(r) for r in rows]
    table_digest = compute_table_digest(row_digests)

    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client._project_id(),
            rows=rows,
            expected_digest=table_digest,
        )
    )

    # Should not raise
    res = client.server.table_create(req)
    assert res.digest == table_digest


# ---------------------------------------------------------------------------
# Regression tests for concurrency / closure fixes
# ---------------------------------------------------------------------------


def test_fast_path_closure_captures_project_eagerly(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    """Regression: the deferred send_obj_create must use the project_id captured
    at save time, not whatever self.project is when the closure eventually runs.
    """
    original_project = client.project

    # Intercept obj_create to record the project_id used.
    captured_project_ids: list[str] = []
    original_obj_create = client.server.server.obj_create

    def recording_obj_create(req: tsi.ObjCreateReq):
        captured_project_ids.append(req.obj.project_id)
        return original_obj_create(req)

    monkeypatch.setattr(client.server.server, "obj_create", recording_obj_create)

    # Save an object while project is "A".
    ref = client._save_object({"data": 1}, "capture_test")

    # Mutate project BEFORE the deferred closure has a chance to run.
    # (In practice the executor may not have started yet.)
    client.project = "mutated-project"

    # Flush forces the deferred closure to execute.
    client._flush()

    # Restore for cleanup.
    client.project = original_project

    # The request must have used the original project, not "mutated-project".
    assert len(captured_project_ids) == 1
    assert captured_project_ids[0] == f"{client.entity}/{original_project}"


@pytest.mark.disable_logging_error_check
def test_concurrent_digest_mismatch_disables_once(
    client: WeaveClient, fast_path: None, monkeypatch, caplog
) -> None:
    """Regression: multiple concurrent mismatches should disable the fast path
    exactly once, and subsequent saves should all use the fallback path.
    """
    original_obj_create = client.server.server.obj_create
    call_count_lock = threading.Lock()
    call_count = 0

    def always_mismatch(req: tsi.ObjCreateReq):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        if req.obj.expected_digest is not None:
            raise DigestMismatchError("forced mismatch")
        return original_obj_create(req)

    monkeypatch.setattr(client.server.server, "obj_create", always_mismatch)
    caplog.set_level(logging.WARNING, logger="weave.trace.weave_client")

    # Fire off a save that will trigger the mismatch.
    weave.publish({"trigger": True}, name="concurrent-mismatch-1")
    client._flush()

    assert client._client_side_digests_disabled_event.is_set()

    # A second save should use the fallback path (expected_digest=None)
    # and succeed without raising.
    ref2 = weave.publish({"after": True}, name="concurrent-mismatch-2")
    client._flush()

    # Verify the second save went through the fallback path.
    got = ref2.get()
    assert got["after"] is True

    # The warning should appear exactly once.
    mismatch_warnings = [
        r
        for r in caplog.records
        if "disabling fast path for this session" in r.getMessage()
    ]
    assert len(mismatch_warnings) == 1
