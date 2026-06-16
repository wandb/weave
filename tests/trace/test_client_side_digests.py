"""Tests for client-side digest correctness.

Verifies that digests computed on the client match those computed on the server
for various object and table shapes, and that the server correctly validates
the expected_digest field.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PIL import Image

import weave
from tests.trace.server_utils import find_server_layer
from weave.shared.digest import (
    compute_file_digest,
    compute_object_digest,
    compute_row_digest,
    compute_table_digest,
)
from weave.trace.settings import (
    UserSettings,
    override_settings,
    replace_settings,
)
from weave.trace.weave_client import (
    CrossProjectRefError,
    NoInternalProjectIDError,
    WeaveClient,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import DigestMismatchError
from weave.trace_server.external_to_internal_trace_server_adapter import (
    ExternalTraceServer,
)


def _configure_digests(client: WeaveClient, *, enable: bool) -> None:
    """Toggle client-side digest computation on or off."""
    replace_settings(UserSettings(enable_client_side_digests=enable))
    client._warm_project_id_resolver()


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


def _make_op():
    """Return a fresh `@weave.op` for publish/digest tests."""

    @weave.op
    def my_test_op(x: int) -> int:
        return x + 1

    return my_test_op


@pytest.fixture
def fast_path(client: WeaveClient):
    """Enable the client-side digest fast path for a test."""
    _configure_digests(client, enable=True)


# Client-side and server-side digests must agree for the same data. Each case
# supplies a factory so dataset/image inputs are rebuilt fresh per publish.
@pytest.mark.parametrize(
    "make",
    [
        lambda: {"model": "gpt-4", "temperature": 0.7, "tags": ["a", "b"]},
        lambda: weave.Dataset(
            name="bench_ds", rows=[{"x": i, "y": str(i)} for i in range(10)]
        ),
        lambda: {
            "config": {"a": 1, "b": [2, 3]},
            "metadata": {"nested": {"deep": True}},
        },
        _make_op,
        lambda: {},
        lambda: {
            "emoji": "\U0001f680\U0001f30d",
            "cjk": "\u4f60\u597d\u4e16\u754c",
            "accent": "\u00e9\u00e0\u00fc",
        },
        lambda: weave.Dataset(
            name="bench_large_ds",
            rows=[
                {"idx": i, "val": f"row_{i}", "data": list(range(i % 10))}
                for i in range(100)
            ],
        ),
        lambda: Image.new("RGB", (16, 16), color=(0, 128, 255)),
    ],
    ids=[
        "object",
        "dataset",
        "nested_object",
        "op",
        "empty_dict",
        "unicode_content",
        "large_dataset",
        "custom_weave_type",
    ],
)
def test_client_server_digest_consistency(
    client: WeaveClient, make: Callable[[], object]
) -> None:
    digest_client = _publish_with_digests(
        client, make(), "consistency_client", enable=True
    )
    digest_server = _publish_with_digests(
        client, make(), "consistency_server", enable=False
    )
    assert digest_client == digest_server


def test_client_server_digest_consistency_with_ref(client: WeaveClient) -> None:
    # Object containing a ref to another object hashes identically both ways.
    inner_ref = weave.publish({"inner_key": "inner_value"}, name="inner_obj")
    client._flush()
    outer = {"ref": inner_ref.uri(), "extra": "data"}

    digest_client = _publish_with_digests(client, outer, "outer_client", enable=True)
    digest_server = _publish_with_digests(client, outer, "outer_server", enable=False)
    assert digest_client == digest_server


def test_republish_same_project_object_keeps_ref(client: WeaveClient) -> None:
    # Re-saving an instance that already carries a same-project ref is a no-op
    # in _save_nested_objects (the ref.project == self.project early return).
    obj = weave.Dataset(name="republish_ds", rows=[{"a": 1}, {"a": 2}])
    first = weave.publish(obj, name="republish_obj")
    client._flush()
    second = weave.publish(obj, name="republish_obj")
    client._flush()
    assert first.digest == second.digest


def test_client_table_row_digests_match_server(client: WeaveClient) -> None:
    rows = [{"x": i, "y": str(i)} for i in range(5)]
    client_row_digests = [compute_row_digest(r) for r in rows]
    client_table_digest = compute_table_digest(client_row_digests)

    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(project_id=client.project_id, rows=rows)
    )
    res = client.server.table_create(req)

    assert res.row_digests == client_row_digests
    assert res.digest == client_table_digest


# Publish via the fast path, read back, verify data is intact across types.
def test_data_correctness_scalar_and_nested_objects(
    client: WeaveClient, fast_path: None
) -> None:
    flat = weave.publish(
        {"key": "value", "number": 42, "list": [1, 2, 3]}, name="round_trip_obj"
    )
    nested = weave.publish(
        {"config": {"a": 1, "b": [2, 3]}, "metadata": {"nested": {"deep": True}}},
        name="nested_rt",
    )
    empty = weave.publish({}, name="empty_rt")
    unicode_ref = weave.publish(
        {"emoji": "\U0001f680", "cjk": "\u4f60\u597d"}, name="unicode_rt"
    )
    client._flush()

    flat_got = flat.get()
    assert flat_got["key"] == "value"
    assert flat_got["number"] == 42
    assert flat_got["list"] == [1, 2, 3]

    nested_got = nested.get()
    assert nested_got["config"]["a"] == 1
    assert nested_got["metadata"]["nested"]["deep"] is True

    assert empty.get() == {}

    unicode_got = unicode_ref.get()
    assert unicode_got["emoji"] == "\U0001f680"
    assert unicode_got["cjk"] == "\u4f60\u597d"


def test_data_correctness_dataset_op_and_image(
    client: WeaveClient, fast_path: None
) -> None:
    ds_ref = weave.publish(
        weave.Dataset(
            name="round_trip_ds", rows=[{"a": i, "b": i * 2} for i in range(5)]
        )
    )
    op_ref = weave.publish(_make_op(), name="op_rt")
    img_ref = weave.publish(
        Image.new("RGB", (32, 32), color=(255, 0, 0)), name="fast_path_image"
    )
    client._flush()

    got_rows = list(ds_ref.get().rows)
    assert len(got_rows) == 5
    for i, row in enumerate(got_rows):
        assert row["a"] == i
        assert row["b"] == i * 2

    assert op_ref.get()(3) == 4

    img_got = img_ref.get()
    assert isinstance(img_got, Image.Image)
    assert img_got.size == (32, 32)
    assert img_got.getpixel((0, 0)) == (255, 0, 0)


def test_data_correctness_get_without_explicit_flush(
    weave_active, fast_path: None
) -> None:
    # ref.get() resolves deferred work via the FutureExecutor, so callers
    # don't need an explicit _flush() (the test client auto-flushes).
    ref = weave.publish({"immediate": "access", "count": 99}, name="no-flush-get-test")
    got = ref.get()
    assert got["immediate"] == "access"
    assert got["count"] == 99


# Server must reject a wrong expected_digest and accept a correct one.
@pytest.mark.parametrize("correct", [True, False], ids=["correct", "wrong"])
def test_server_digest_validation_object(client: WeaveClient, correct: bool) -> None:
    val = {"hello": "world"}
    expected_digest = compute_object_digest(val) if correct else "definitely_wrong"
    req = tsi.ObjCreateReq(
        obj=tsi.ObjSchemaForInsert(
            project_id=client.project_id,
            object_id="digest_obj",
            val=val,
            expected_digest=expected_digest,
        )
    )
    if correct:
        assert client.server.obj_create(req).digest == expected_digest
    else:
        with pytest.raises(DigestMismatchError):
            client.server.obj_create(req)


@pytest.mark.parametrize("correct", [True, False], ids=["correct", "wrong"])
def test_server_digest_validation_table(client: WeaveClient, correct: bool) -> None:
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    row_digests = [compute_row_digest(r) for r in rows]
    expected_digest = (
        compute_table_digest(row_digests) if correct else "definitely_wrong"
    )
    req = tsi.TableCreateReq(
        table=tsi.TableSchemaForInsert(
            project_id=client.project_id, rows=rows, expected_digest=expected_digest
        )
    )
    if correct:
        res = client.server.table_create(req)
        assert res.digest == expected_digest
        assert res.row_digests == row_digests
    else:
        with pytest.raises(DigestMismatchError):
            client.server.table_create(req)


@pytest.mark.parametrize("correct", [True, False], ids=["correct", "wrong"])
def test_server_digest_validation_file(client: WeaveClient, correct: bool) -> None:
    content = b"hello world"
    expected_digest = compute_file_digest(content) if correct else "definitely_wrong"
    req = tsi.FileCreateReq(
        project_id=client.project_id,
        name="test.txt",
        content=content,
        expected_digest=expected_digest,
    )
    if correct:
        assert client.server.file_create(req).digest == expected_digest
    else:
        with pytest.raises(DigestMismatchError):
            client.server.file_create(req)


# _convert_refs_to_internal unit behavior.
def test_convert_refs_raises_when_no_internal_id(client: WeaveClient) -> None:
    # Resolver returns None when the flag is off (default), so conversion raises.
    json_val = {
        "key": "value",
        "ref": f"weave:///{client.entity}/{client.project}/object/foo:abc123",
    }
    with (
        override_settings(enable_client_side_digests=False),
        pytest.raises(NoInternalProjectIDError),
    ):
        client._convert_refs_to_internal(json_val)


def test_convert_refs_raises_for_cross_project_ref(
    client: WeaveClient, fast_path: None
) -> None:
    json_val = {
        "same_project": f"weave:///{client.entity}/{client.project}/object/foo:abc123",
        "cross_project": f"weave:///{client.entity}/other-project/object/bar:def456",
    }
    with pytest.raises(CrossProjectRefError):
        client._convert_refs_to_internal(json_val)


def test_cross_project_ref_skips_expected_digest(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    # An unresolvable cross-project ref makes the caller skip expected_digest
    # and let the server compute the digest instead.
    captured: list[str | None] = []
    adapter = find_server_layer(client.server, ExternalTraceServer)
    original = type(adapter).obj_create

    def spy(self, req):
        captured.append(req.obj.expected_digest)
        return original(self, req)

    monkeypatch.setattr(type(adapter), "obj_create", spy)

    original_project = client.project
    client.project = "other-project"
    inner_ref = client._save_object({"msg": "hi"}, "inner")
    client._flush()

    client.project = original_project
    weave.publish(
        {"cross_ref": inner_ref.uri(), "data": "test"}, name="outer-with-cross-ref"
    )
    client._flush()

    assert len(captured) >= 1
    assert captured[-1] is None


# On DigestMismatchError the client retries without expected_digest and
# disables client-side digests for the rest of the session.
@pytest.mark.disable_logging_error_check
def test_object_mismatch_retries_and_disables(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    adapter = find_server_layer(client.server, ExternalTraceServer)
    original = adapter.obj_create
    seen_digests: list[str | None] = []
    injected = False

    def mismatch_once(req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        nonlocal injected
        seen_digests.append(req.obj.expected_digest)
        if not injected and req.obj.expected_digest is not None:
            injected = True
            raise DigestMismatchError("forced mismatch")
        return original(req)

    monkeypatch.setattr(adapter, "obj_create", mismatch_once)

    ref = weave.publish({"first": True}, name="mismatch-first")
    client._flush()

    assert seen_digests == [ref.digest, None]
    assert client.project_id_resolver.is_disabled

    seen_digests.clear()
    weave.publish({"second": True}, name="mismatch-second")
    client._flush()
    assert seen_digests == [None]


@pytest.mark.disable_logging_error_check
def test_table_mismatch_retries_and_disables(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    adapter = find_server_layer(client.server, ExternalTraceServer)
    original = adapter.table_create
    injected = False

    def mismatch_once(req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        nonlocal injected
        if not injected and req.table.expected_digest is not None:
            injected = True
            raise DigestMismatchError("forced table mismatch")
        return original(req)

    monkeypatch.setattr(adapter, "table_create", mismatch_once)

    ds = weave.Dataset(name="mismatch-ds", rows=[{"x": 1}, {"x": 2}])
    ref = weave.publish(ds, name="mismatch-ds")
    client._flush()

    assert client.project_id_resolver.is_disabled
    assert len(list(ref.get().rows)) == 2


@pytest.mark.disable_logging_error_check
def test_file_mismatch_retries_and_disables(
    client: WeaveClient, fast_path: None, monkeypatch
) -> None:
    adapter = find_server_layer(client.server, ExternalTraceServer)
    original = adapter.file_create
    injected = False

    def mismatch_once(req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        nonlocal injected
        if not injected and req.expected_digest is not None:
            injected = True
            raise DigestMismatchError("forced file mismatch")
        return original(req)

    monkeypatch.setattr(adapter, "file_create", mismatch_once)

    weave.publish(Image.new("RGB", (2, 2), color="red"), name="mismatch-img")
    client._flush()
    assert client.project_id_resolver.is_disabled
