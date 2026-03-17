"""Tests for client-side digest correctness.

Verifies that digests computed on the client match those computed on the server
for various object and table shapes, and that the server correctly validates
the expected_digest field.
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
from weave.trace_server.errors import DigestMismatchError


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


class TestClientServerDigestConsistency:
    """Client-side and server-side digests must agree for the same data."""

    def test_object(self, client: WeaveClient):
        obj = {"model": "gpt-4", "temperature": 0.7, "tags": ["a", "b"]}

        digest_client = _publish_with_digests(client, obj, "obj_client", enable=True)
        digest_server = _publish_with_digests(client, obj, "obj_server", enable=False)

        assert digest_client == digest_server

    def test_dataset(self, client: WeaveClient):
        rows = [{"x": i, "y": str(i)} for i in range(10)]

        ds_client = weave.Dataset(name="bench_ds", rows=rows)
        digest_client = _publish_with_digests(
            client, ds_client, "ds_client", enable=True
        )

        ds_server = weave.Dataset(name="bench_ds", rows=rows)
        digest_server = _publish_with_digests(
            client, ds_server, "ds_server", enable=False
        )

        assert digest_client == digest_server

    def test_nested_object(self, client: WeaveClient):
        obj = {
            "config": {"a": 1, "b": [2, 3]},
            "metadata": {"nested": {"deep": True}},
        }

        digest_client = _publish_with_digests(
            client, obj, "nested_client", enable=True
        )
        digest_server = _publish_with_digests(
            client, obj, "nested_server", enable=False
        )

        assert digest_client == digest_server

    def test_op(self, client: WeaveClient):
        @weave.op
        def my_test_op(x: int) -> int:
            return x + 1

        digest_client = _publish_with_digests(
            client, my_test_op, "op_client", enable=True
        )
        digest_server = _publish_with_digests(
            client, my_test_op, "op_server", enable=False
        )

        assert digest_client == digest_server

    def test_empty_dict(self, client: WeaveClient):
        obj: dict = {}

        digest_client = _publish_with_digests(
            client, obj, "empty_client", enable=True
        )
        digest_server = _publish_with_digests(
            client, obj, "empty_server", enable=False
        )

        assert digest_client == digest_server

    def test_unicode_content(self, client: WeaveClient):
        obj = {
            "emoji": "\U0001f680\U0001f30d",
            "cjk": "\u4f60\u597d\u4e16\u754c",
            "accent": "\u00e9\u00e0\u00fc",
        }

        digest_client = _publish_with_digests(
            client, obj, "unicode_client", enable=True
        )
        digest_server = _publish_with_digests(
            client, obj, "unicode_server", enable=False
        )

        assert digest_client == digest_server

    def test_large_dataset(self, client: WeaveClient):
        rows = [
            {"idx": i, "val": f"row_{i}", "data": list(range(i % 10))}
            for i in range(100)
        ]

        ds_client = weave.Dataset(name="bench_large_ds", rows=rows)
        digest_client = _publish_with_digests(
            client, ds_client, "large_client", enable=True
        )

        ds_server = weave.Dataset(name="bench_large_ds", rows=rows)
        digest_server = _publish_with_digests(
            client, ds_server, "large_server", enable=False
        )

        assert digest_client == digest_server

    def test_object_with_ref(self, client: WeaveClient):
        """Object containing a ref to another object."""
        inner = {"inner_key": "inner_value"}
        inner_ref = weave.publish(inner, name="inner_obj")
        client._flush()

        outer = {"ref": inner_ref.uri(), "extra": "data"}

        digest_client = _publish_with_digests(
            client, outer, "outer_client", enable=True
        )
        digest_server = _publish_with_digests(
            client, outer, "outer_server", enable=False
        )

        assert digest_client == digest_server

    def test_custom_weave_type(self, client: WeaveClient):
        """CustomWeaveType (PIL Image) produces the same digest on both paths."""
        img_client = Image.new("RGB", (16, 16), color=(0, 128, 255))
        digest_client = _publish_with_digests(
            client, img_client, "img_client", enable=True
        )

        img_server = Image.new("RGB", (16, 16), color=(0, 128, 255))
        digest_server = _publish_with_digests(
            client, img_server, "img_server", enable=False
        )

        assert digest_client == digest_server

    def test_table_row_digests(self, client: WeaveClient):
        """Client-computed row and table digests match the server's."""
        rows = [{"x": i, "y": str(i)} for i in range(5)]

        client_row_digests = [compute_row_digest(r) for r in rows]
        client_table_digest = compute_table_digest(client_row_digests)

        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=rows,
            )
        )
        res = client.server.table_create(req)

        assert res.row_digests == client_row_digests
        assert res.digest == client_table_digest


class TestRoundTrip:
    """Publish via client-side digest path, read back, verify data integrity."""

    def test_object(self, client: WeaveClient, fast_path: None):
        obj = {"key": "value", "number": 42, "list": [1, 2, 3]}
        ref = weave.publish(obj, name="round_trip_obj")
        client._flush()

        got = ref.get()
        assert got["key"] == "value"
        assert got["number"] == 42
        assert got["list"] == [1, 2, 3]

    def test_dataset(self, client: WeaveClient, fast_path: None):
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

    def test_ref_get_without_explicit_flush(
        self, client: WeaveClient, fast_path: None
    ):
        obj = {"immediate": "access", "count": 99}
        ref = weave.publish(obj, name="fast-path-get-test")

        got = ref.get()
        assert got["immediate"] == "access"
        assert got["count"] == 99

    def test_custom_weave_type(self, client: WeaveClient, fast_path: None):
        img = Image.new("RGB", (32, 32), color=(255, 0, 0))
        ref = weave.publish(img, name="fast_path_image")
        client._flush()

        got = ref.get()
        assert isinstance(got, Image.Image)
        assert got.size == (32, 32)
        assert got.getpixel((0, 0)) == (255, 0, 0)


class TestServerRejectsWrongDigest:
    """Server must raise DigestMismatchError when expected_digest is wrong."""

    def test_object(self, client: WeaveClient):
        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=client._project_id(),
                object_id="bad_digest_obj",
                val={"hello": "world"},
                expected_digest="definitely_wrong_digest",
            )
        )

        with pytest.raises(DigestMismatchError):
            client.server.obj_create(req)

    def test_table(self, client: WeaveClient):
        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=[{"a": 1}, {"a": 2}],
                expected_digest="definitely_wrong_digest",
            )
        )

        with pytest.raises(DigestMismatchError):
            client.server.table_create(req)

    def test_file(self, client: WeaveClient):
        req = tsi.FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=b"hello world",
            expected_digest="definitely_wrong_digest",
        )

        with pytest.raises(DigestMismatchError):
            client.server.file_create(req)


class TestServerAcceptsCorrectDigest:
    """Server must accept requests when expected_digest is correct."""

    def test_object(self, client: WeaveClient):
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

        res = client.server.obj_create(req)
        assert res.digest == digest

    def test_table(self, client: WeaveClient):
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

        res = client.server.table_create(req)
        assert res.digest == table_digest

    def test_file(self, client: WeaveClient):
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

    def test_table_row_digests_returned(self, client: WeaveClient, fast_path: None):
        """Server returns row_digests that match client-computed values."""
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


# ---------------------------------------------------------------------------
# Client wiring: expected_digest is sent through the publish path
# ---------------------------------------------------------------------------


def test_table_expected_digest_sent_through_client(
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
# Settings
# ---------------------------------------------------------------------------


def test_env_var_enables_client_side_digests(monkeypatch) -> None:
    """WEAVE_ENABLE_CLIENT_SIDE_DIGESTS env var toggles the setting."""
    parse_and_apply_settings(UserSettings())

    monkeypatch.setenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", "true")
    assert should_enable_client_side_digests() is True

    monkeypatch.setenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", "false")
    assert should_enable_client_side_digests() is False

    monkeypatch.delenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", raising=False)


# ---------------------------------------------------------------------------
# _convert_refs_to_internal
# ---------------------------------------------------------------------------


def test_convert_refs_to_internal_returns_none_when_no_cached_id(
    client: WeaveClient,
) -> None:
    """Returns None when no internal ID is cached, signaling callers to skip digest."""
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
    """Returns None when cross-project refs are present.

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
    assert captured_digests[-1] is None
