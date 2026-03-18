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
from weave.shared.digest import (
    compute_file_digest,
    compute_object_digest,
    compute_row_digest,
    compute_table_digest,
)
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
)
from weave.trace.weave_client import (
    CrossProjectRefError,
    NoInternalProjectIDError,
    WeaveClient,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import DigestMismatchError


def _compute_test_internal_project_id(client: WeaveClient) -> str:
    """Compute the internal project ID that the test DummyIdConverter produces.

    In tests, DummyIdConverter maps entity/project -> base64(entity/project).
    """
    ext_id = f"{client.entity}/{client.project}"
    return base64.b64encode(ext_id.encode()).decode()


def _configure_digests(client: WeaveClient, *, enable: bool) -> None:
    """Apply digest settings and configure the resolver for tests.

    In test environments, ``projects_info`` is not available on the local
    server chain (it lives on ``ServiceInterface``, a remote-only concern).
    The multi-layer delegation (ServerRecorder → CachingMiddleware →
    ExternalToInternal adapter) makes clean mocking impractical, so we set
    the resolver state directly.
    """
    parse_and_apply_settings(UserSettings(enable_client_side_digests=enable))
    if enable:
        # Re-enable the resolver (it gets permanently disabled during
        # __init__ because projects_info raises AttributeError on the
        # local server chain) and populate the internal project ID cache.
        client.project_id_resolver._disabled_event.clear()
        client._cached_internal_project_id = _compute_test_internal_project_id(
            client
        )
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


def _inner_server(client: WeaveClient) -> tsi.TraceServerInterface:
    """Unwrap the ServerRecorder to get the CachingMiddlewareTraceServer.

    In tests, client.server is a ServerRecorder that delegates to
    the CachingMiddlewareTraceServer. This helper avoids reaching
    through .server.server in every test.
    """
    return client.server.server


def _spy_on_server_method(
    client: WeaveClient,
    method_name: str,
    captured: list,
    extract_fn,
    monkeypatch,
) -> None:
    """Install a spy on a server method that captures values via extract_fn.

    The test server chain uses DelegatingTraceServerMixin with a custom
    __getattribute__ that ignores instance attributes for class-defined
    methods. To intercept reliably, we find the LOWEST concrete class in
    the delegation chain that defines the method and patch there.

    We check the delegated server first (ExternalToInternal adapter) because
    it's lower in the chain — patching a Protocol/ABC base like
    TraceServerInterface would be shadowed by the concrete implementation.
    """
    server = _inner_server(client)

    # Check delegated server first (lower = more concrete), then the wrapper.
    for srv in [server._next_trace_server, server]:
        for cls in type(srv).__mro__:
            if cls is object:
                continue
            if method_name in cls.__dict__:
                original = cls.__dict__[method_name]

                def spy(self, req, _orig=original):
                    captured.append(extract_fn(req))
                    return _orig(self, req)

                monkeypatch.setattr(cls, method_name, spy)
                return

    raise ValueError(f"Could not find {method_name} in server chain")


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


class TestDataCorrectness:
    """Publish via client-side digest path, read back, verify data is intact."""

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

    def test_nested_object(self, client: WeaveClient, fast_path: None):
        obj = {
            "config": {"a": 1, "b": [2, 3]},
            "metadata": {"nested": {"deep": True}},
        }
        ref = weave.publish(obj, name="nested_rt")
        client._flush()

        got = ref.get()
        assert got["config"]["a"] == 1
        assert got["metadata"]["nested"]["deep"] is True

    def test_op(self, client: WeaveClient, fast_path: None):
        @weave.op
        def my_rt_op(x: int) -> int:
            return x + 1

        ref = weave.publish(my_rt_op, name="op_rt")
        client._flush()

        got = ref.get()
        assert got(3) == 4

    def test_empty_dict(self, client: WeaveClient, fast_path: None):
        ref = weave.publish({}, name="empty_rt")
        client._flush()
        assert ref.get() == {}

    def test_unicode_content(self, client: WeaveClient, fast_path: None):
        obj = {"emoji": "\U0001f680", "cjk": "\u4f60\u597d"}
        ref = weave.publish(obj, name="unicode_rt")
        client._flush()

        got = ref.get()
        assert got["emoji"] == "\U0001f680"
        assert got["cjk"] == "\u4f60\u597d"

    def test_custom_weave_type(self, client: WeaveClient, fast_path: None):
        img = Image.new("RGB", (32, 32), color=(255, 0, 0))
        ref = weave.publish(img, name="fast_path_image")
        client._flush()

        got = ref.get()
        assert isinstance(got, Image.Image)
        assert got.size == (32, 32)
        assert got.getpixel((0, 0)) == (255, 0, 0)

    def test_get_without_explicit_flush(self, client: WeaveClient, fast_path: None):
        """ref.get() must work without an explicit _flush() call.

        In production, the FutureExecutor resolves deferred work when the
        digest or data is accessed. The test client auto-flushes, but this
        test documents the contract that callers don't need to flush manually.
        """
        obj = {"immediate": "access", "count": 99}
        ref = weave.publish(obj, name="no-flush-get-test")

        got = ref.get()
        assert got["immediate"] == "access"
        assert got["count"] == 99


class TestServerDigestValidation:
    """Server must reject wrong expected_digest and accept correct ones."""

    def test_object_wrong_digest(self, client: WeaveClient):
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

    def test_table_wrong_digest(self, client: WeaveClient):
        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=[{"a": 1}, {"a": 2}],
                expected_digest="definitely_wrong_digest",
            )
        )

        with pytest.raises(DigestMismatchError):
            client.server.table_create(req)

    def test_file_wrong_digest(self, client: WeaveClient):
        req = tsi.FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=b"hello world",
            expected_digest="definitely_wrong_digest",
        )

        with pytest.raises(DigestMismatchError):
            client.server.file_create(req)

    def test_object_correct_digest(self, client: WeaveClient):
        val = {"server": "accepts", "this": True}
        expected_digest = compute_object_digest(val)

        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=client._project_id(),
                object_id="correct_digest_obj",
                val=val,
                expected_digest=expected_digest,
            )
        )

        res = client.server.obj_create(req)
        assert res.digest == expected_digest

    def test_table_correct_digest(self, client: WeaveClient):
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}]
        row_digests = [compute_row_digest(r) for r in rows]
        expected_digest = compute_table_digest(row_digests)

        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client._project_id(),
                rows=rows,
                expected_digest=expected_digest,
            )
        )

        res = client.server.table_create(req)
        assert res.digest == expected_digest
        assert res.row_digests == row_digests

    def test_file_correct_digest(self, client: WeaveClient):
        content = b"hello world"
        expected_digest = compute_file_digest(content)

        req = tsi.FileCreateReq(
            project_id=client._project_id(),
            name="test.txt",
            content=content,
            expected_digest=expected_digest,
        )

        res = client.server.file_create(req)
        assert res.digest == expected_digest


class TestExpectedDigestWiring:
    """Verify that the client sends (or omits) expected_digest correctly."""

    def test_fast_path_sends_object_expected_digest(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        captured: list[str | None] = []
        _spy_on_server_method(
            client, "obj_create", captured,
            lambda req: req.obj.expected_digest, monkeypatch,
        )

        weave.publish({"test": "fast_path"}, name="fast-path-test")
        client._flush()

        assert len(captured) == 1
        assert captured[0] is not None

    def test_fallback_omits_object_expected_digest(
        self, client: WeaveClient, monkeypatch
    ) -> None:
        captured: list[str | None] = []
        _spy_on_server_method(
            client, "obj_create", captured,
            lambda req: req.obj.expected_digest, monkeypatch,
        )

        weave.publish({"test": "fallback_path"}, name="fallback-path-test")
        client._flush()

        assert len(captured) == 1
        assert captured[0] is None

    def test_fast_path_sends_table_expected_digest(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        captured: list[str | None] = []
        _spy_on_server_method(
            client, "table_create", captured,
            lambda req: req.table.expected_digest, monkeypatch,
        )

        ds = weave.Dataset(name="table_digest_test", rows=[{"x": 1}])
        weave.publish(ds, name="table-digest-test")
        client._flush()

        assert any(d is not None for d in captured)

    def test_fallback_omits_table_expected_digest(
        self, client: WeaveClient, monkeypatch
    ) -> None:
        captured: list[str | None] = []
        _spy_on_server_method(
            client, "table_create", captured,
            lambda req: req.table.expected_digest, monkeypatch,
        )

        ds = weave.Dataset(name="table_no_digest", rows=[{"x": 1}])
        weave.publish(ds, name="table-no-digest-test")
        client._flush()

        assert all(d is None for d in captured)

    def test_file_expected_digest_sent_for_custom_type(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        captured: list[str | None] = []
        _spy_on_server_method(
            client, "file_create", captured,
            lambda req: req.expected_digest, monkeypatch,
        )

        img = Image.new("RGB", (4, 4), color="blue")
        weave.publish(img, name="file-digest-image")
        client._flush()

        assert len(captured) >= 1
        assert all(d is not None for d in captured)


class TestConvertRefsToInternal:
    """Unit tests for _convert_refs_to_internal."""

    def test_raises_when_no_cached_id(self, client: WeaveClient) -> None:
        """Raises NoInternalProjectIDError when no internal ID is cached."""
        client._cached_internal_project_id = None

        json_val = {
            "key": "value",
            "ref": f"weave:///{client.entity}/{client.project}/object/foo:abc123",
        }

        with pytest.raises(NoInternalProjectIDError):
            client._convert_refs_to_internal(json_val)

    def test_raises_for_cross_project_ref(
        self, client: WeaveClient, fast_path: None
    ) -> None:
        """Raises CrossProjectRefError when cross-project refs are present."""
        json_val = {
            "same_project": f"weave:///{client.entity}/{client.project}/object/foo:abc123",
            "cross_project": f"weave:///{client.entity}/other-project/object/bar:def456",
        }

        with pytest.raises(CrossProjectRefError):
            client._convert_refs_to_internal(json_val)

    def test_cross_project_ref_skips_expected_digest(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        """Publishing with a cross-project ref falls back to no expected_digest.

        When the client encounters an unresolvable cross-project ref, it raises
        CrossProjectRefError which is caught by the caller, causing it to skip
        expected_digest and let the server compute the digest instead.
        """
        captured: list[str | None] = []
        _spy_on_server_method(
            client, "obj_create", captured,
            lambda req: req.obj.expected_digest, monkeypatch,
        )

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
        assert len(captured) >= 1
        assert captured[-1] is None
