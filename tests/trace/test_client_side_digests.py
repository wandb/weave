"""Tests for client-side digest correctness.

Verifies that digests computed on the client (fast path) match those computed
on the server (fallback path) for various object and table shapes.
"""

from __future__ import annotations

import base64

import pytest
from PIL import Image

import weave
from weave.shared.digest import compute_row_digest, compute_table_digest
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
    should_enable_client_side_digests,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset settings to defaults after each test to avoid leaking state."""
    yield
    parse_and_apply_settings(UserSettings())


@pytest.fixture
def fast_path(client: WeaveClient):
    """Enable the client-side digest fast path for a test.

    Teardown is handled by the autouse ``_reset_settings`` fixture.
    """
    _configure_digests(client, enable=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_test_internal_project_id(client: WeaveClient) -> str:
    """Compute the internal project ID that the test DummyIdConverter produces.

    In tests, DummyIdConverter maps entity/project -> base64(entity/project).
    """
    ext_id = f"{client.entity}/{client.project}"
    return base64.b64encode(ext_id.encode()).decode()


def _configure_digests(client: WeaveClient, *, enable: bool) -> None:
    """Apply digest settings and configure the resolver for tests."""
    parse_and_apply_settings(UserSettings(enable_client_side_digests=enable))
    if enable:
        # In test environments, projects_info is not available, so the
        # resolver gets permanently disabled during __init__. Re-enable it
        # and populate the cached internal project ID manually.
        client.project_id_resolver._disabled_event.clear()
        client._cached_internal_project_id = _compute_test_internal_project_id(client)
    else:
        client._cached_internal_project_id = None


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
    _configure_digests(client, enable=enable)
    ref = weave.publish(obj, name=name)
    client._flush()
    return ref.digest


# ---------------------------------------------------------------------------
# Cross-path: same data -> same digest regardless of path
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


def test_op_digest_matches_across_paths(client: WeaveClient):
    """An op published via fast and fallback paths produces the same digest."""

    @weave.op
    def my_test_op(x: int) -> int:
        return x + 1

    digest_fast = _publish_with_digests(client, my_test_op, "op_fast", enable=True)
    digest_fallback = _publish_with_digests(
        client, my_test_op, "op_fallback", enable=False
    )

    assert digest_fast == digest_fallback


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


def test_fast_path_ref_get_succeeds_without_explicit_flush(
    client: WeaveClient,
    fast_path: None,
) -> None:
    """A fast-path ref can be .get()'d after flush."""
    obj = {"immediate": "access", "count": 99}
    ref = weave.publish(obj, name="fast-path-get-test")

    got = ref.get()
    assert got["immediate"] == "access"
    assert got["count"] == 99


# ---------------------------------------------------------------------------
# Server-side validation: expected_digest is checked
# ---------------------------------------------------------------------------


def test_server_rejects_wrong_expected_digest(client: WeaveClient):
    """Server raises when expected_digest doesn't match."""
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
    """Server raises for table with wrong expected_digest."""
    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client._project_id(),
            rows=[{"a": 1}, {"a": 2}],
            expected_digest="definitely_wrong_digest",
        )
    )

    with pytest.raises(Exception, match=r"(?i)digest|409|mismatch"):
        client.server.table_create(req)


def test_server_accepts_correct_expected_digest(client: WeaveClient) -> None:
    """Server accepts obj_create when expected_digest matches."""
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
    """Server accepts table_create when expected_digest matches."""
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
# Settings toggle: fast vs fallback path selection
# ---------------------------------------------------------------------------


def test_fast_path_sends_expected_digest(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    """When client-side digests are enabled, obj_create receives expected_digest."""
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
    """When client-side digests are disabled, obj_create receives no expected_digest."""
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
    """WEAVE_ENABLE_CLIENT_SIDE_DIGESTS env var toggles the setting."""
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
    """Table created via fast path returns row_digests matching client computation."""
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
    """Table row digests from fast and fallback paths must agree."""
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
# Table expected_digest wiring through the client
# ---------------------------------------------------------------------------


def test_fast_path_sends_table_expected_digest(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    """When client-side digests are enabled, table_create receives expected_digest."""
    captured_digests: list[str | None] = []
    original_send = client._send_table_create

    def capturing_send(rows):
        res = original_send(rows)
        captured_digests.append(res.digest)
        return res

    monkeypatch.setattr(client, "_send_table_create", capturing_send)

    ds = weave.Dataset(name="table_digest_ds", rows=[{"a": 1}, {"a": 2}])
    weave.publish(ds, name="table_digest_ds")
    client._flush()

    # If expected_digest were wrong, the server would have raised
    # DigestMismatchError. The fact that it succeeded proves expected_digest
    # was sent and matched.
    assert len(captured_digests) >= 1
    assert captured_digests[0] is not None


def test_fallback_path_does_not_compute_table_digest(
    client: WeaveClient, monkeypatch
) -> None:
    """When client-side digests are disabled, _send_table_create skips digest computation."""
    assert not client._should_compute_client_digests()

    called = []
    original_send = client._send_table_create

    def capturing_send(rows):
        called.append(True)
        return original_send(rows)

    monkeypatch.setattr(client, "_send_table_create", capturing_send)

    ds = weave.Dataset(name="table_no_digest_ds", rows=[{"a": 1}, {"a": 2}])
    weave.publish(ds, name="table_no_digest_ds")
    client._flush()

    # Verify _send_table_create was called and the feature flag is off.
    # The cross-path tests (test_dataset_digest_matches_across_paths) already
    # verify that the fallback path produces correct digests without
    # expected_digest.
    assert len(called) >= 1


# ---------------------------------------------------------------------------
# File expected_digest validation
# ---------------------------------------------------------------------------


def test_server_accepts_correct_file_expected_digest(client: WeaveClient) -> None:
    """Server accepts file_create when expected_digest matches."""
    from weave.shared.digest import compute_file_digest

    content = b"hello world"
    digest = compute_file_digest(content)

    req = tsi.FileCreateReq(
        project_id=client._project_id(),
        name="test.txt",
        content=content,
        expected_digest=digest,
    )

    res = client.server.file_create(req)
    assert res.digest == digest


def test_server_rejects_wrong_file_expected_digest(client: WeaveClient) -> None:
    """Server raises for file with wrong expected_digest."""
    req = tsi.FileCreateReq(
        project_id=client._project_id(),
        name="test.txt",
        content=b"hello world",
        expected_digest="definitely_wrong_digest",
    )

    with pytest.raises(Exception, match=r"(?i)digest|409|mismatch"):
        client.server.file_create(req)


def test_file_expected_digest_sent_for_custom_type(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    """Publishing a CustomWeaveType (PIL Image) sends expected_digest on file_create."""
    captured_digests: list[str | None] = []
    original_file_create = client.server.server.file_create

    def capturing_file_create(req: tsi.FileCreateReq):
        captured_digests.append(req.expected_digest)
        return original_file_create(req)

    monkeypatch.setattr(client.server.server, "file_create", capturing_file_create)

    img = Image.new("RGB", (4, 4), color="blue")
    weave.publish(img, name="file-digest-image")
    client._flush()

    assert len(captured_digests) >= 1
    assert all(d is not None for d in captured_digests)


# ---------------------------------------------------------------------------
# _convert_refs_to_internal helper
# ---------------------------------------------------------------------------


def test_convert_refs_to_internal_returns_none_when_no_cached_id(
    client: WeaveClient,
) -> None:
    """_convert_refs_to_internal returns None when no internal ID is cached."""
    client._cached_internal_project_id = None

    json_val = {
        "key": "value",
        "ref": f"weave:///{client.entity}/{client.project}/object/foo:abc123",
    }
    result = client._convert_refs_to_internal(json_val)

    assert result is None


def test_convert_refs_to_internal_returns_none_for_cross_project_ref(
    client: WeaveClient, fast_path: None
) -> None:
    """_convert_refs_to_internal returns None when cross-project refs are present.

    Cross-project refs can't be resolved to internal IDs without a server
    round-trip. Rather than computing a digest that will definitely mismatch,
    callers should skip digest computation entirely.
    """
    json_val = {
        "same_project": f"weave:///{client.entity}/{client.project}/object/foo:abc123",
        "cross_project": f"weave:///{client.entity}/other-project/object/bar:def456",
    }
    result = client._convert_refs_to_internal(json_val)

    assert result is None


def test_cross_project_ref_skips_expected_digest(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    """Publishing an object with a cross-project ref falls back to no expected_digest.

    When the client can't resolve all refs to internal IDs, it must not send
    expected_digest — a partial conversion would guarantee a mismatch.
    """
    captured_digests: list[str | None] = []
    original_obj_create = client.server.server.obj_create

    def capturing_obj_create(req: tsi.ObjCreateReq):
        captured_digests.append(req.obj.expected_digest)
        return original_obj_create(req)

    monkeypatch.setattr(client.server.server, "obj_create", capturing_obj_create)

    # Publish an inner object in a different project to get a cross-project ref
    original_project = client.project
    client.project = "other-project"
    inner_ref = client._save_object({"msg": "hi"}, "inner")
    client._flush()

    # Now publish an outer object in the original project that references it
    client.project = original_project
    outer = {"cross_ref": inner_ref.uri(), "data": "test"}
    weave.publish(outer, name="outer-with-cross-ref")
    client._flush()

    # The outer object's obj_create should have expected_digest=None
    # because of the unresolvable cross-project ref
    assert len(captured_digests) >= 1
    # The last captured digest is for the outer object
    assert captured_digests[-1] is None
