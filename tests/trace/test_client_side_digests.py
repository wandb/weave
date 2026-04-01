"""Tests for client-side digest correctness.

Verifies that digests computed on the client match those computed on the server
for various object and table shapes, and that the server correctly validates
the expected_digest field.
"""

from __future__ import annotations

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
    parse_and_apply_settings,
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
    parse_and_apply_settings(UserSettings(enable_client_side_digests=enable))
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


@pytest.fixture
def fast_path(client: WeaveClient):
    """Enable the client-side digest fast path for a test."""
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

        digest_client = _publish_with_digests(client, obj, "nested_client", enable=True)
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

        digest_client = _publish_with_digests(client, obj, "empty_client", enable=True)
        digest_server = _publish_with_digests(client, obj, "empty_server", enable=False)

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
                project_id=client.project_id,
                rows=rows,
            )
        )
        res = client.server.table_create(req)

        assert res.row_digests == client_row_digests
        assert res.digest == client_table_digest


class TestDataCorrectness:
    """Publish (client-side and server-side), read back, verify data is intact."""

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

    @pytest.mark.parametrize("correct", [True, False], ids=["correct", "wrong"])
    def test_object(self, client: WeaveClient, correct: bool):
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
            res = client.server.obj_create(req)
            assert res.digest == expected_digest
        else:
            with pytest.raises(DigestMismatchError):
                client.server.obj_create(req)

    @pytest.mark.parametrize("correct", [True, False], ids=["correct", "wrong"])
    def test_table(self, client: WeaveClient, correct: bool):
        rows = [{"a": 1}, {"a": 2}, {"a": 3}]
        row_digests = [compute_row_digest(r) for r in rows]
        expected_digest = (
            compute_table_digest(row_digests) if correct else "definitely_wrong"
        )

        req = tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=client.project_id,
                rows=rows,
                expected_digest=expected_digest,
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
    def test_file(self, client: WeaveClient, correct: bool):
        content = b"hello world"
        expected_digest = (
            compute_file_digest(content) if correct else "definitely_wrong"
        )

        req = tsi.FileCreateReq(
            project_id=client.project_id,
            name="test.txt",
            content=content,
            expected_digest=expected_digest,
        )

        if correct:
            res = client.server.file_create(req)
            assert res.digest == expected_digest
        else:
            with pytest.raises(DigestMismatchError):
                client.server.file_create(req)


class TestConvertRefsToInternal:
    """Unit tests for _convert_refs_to_internal."""

    def test_raises_when_no_internal_id(self, client: WeaveClient) -> None:
        """Raises NoInternalProjectIDError when the resolver returns None.

        This happens when the feature flag is off (default) or the resolver
        is disabled — get_internal_project_id returns None.
        """
        # Ensure the setting is off so the resolver returns None
        parse_and_apply_settings(UserSettings(enable_client_side_digests=False))

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
        # Spy on the adapter's obj_create to capture expected_digest values
        captured: list[str | None] = []
        adapter = find_server_layer(client.server, ExternalTraceServer)
        original = type(adapter).obj_create

        def spy(self, req):
            captured.append(req.obj.expected_digest)
            return original(self, req)

        monkeypatch.setattr(type(adapter), "obj_create", spy)

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


class TestDigestMismatchAutoDisable:
    """On DigestMismatchError the client retries without expected_digest
    and disables client-side digests for the rest of the session.
    """

    @pytest.mark.disable_logging_error_check
    def test_object_mismatch_retries_and_disables(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        """First obj_create with expected_digest fails; client retries without
        it and disables fast path for subsequent saves.
        """
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

        # First publish: expected_digest sent, server rejects, client retries
        ref = weave.publish({"first": True}, name="mismatch-first")
        client._flush()

        # Should have seen: [digest, None] (first attempt + retry)
        assert seen_digests == [ref.digest, None]
        assert client.project_id_resolver.is_disabled

        # Second publish: fast path is disabled, no expected_digest
        seen_digests.clear()
        weave.publish({"second": True}, name="mismatch-second")
        client._flush()

        assert seen_digests == [None]

    @pytest.mark.disable_logging_error_check
    def test_table_mismatch_retries_and_disables(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        """Table digest mismatch retries and disables fast path."""
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

        # Data should still be readable (retry succeeded)
        got = ref.get()
        got_rows = list(got.rows)
        assert len(got_rows) == 2

    @pytest.mark.disable_logging_error_check
    def test_file_mismatch_retries_and_disables(
        self, client: WeaveClient, fast_path: None, monkeypatch
    ) -> None:
        """File digest mismatch retries and disables fast path."""
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

        img = Image.new("RGB", (2, 2), color="red")
        weave.publish(img, name="mismatch-img")
        client._flush()

        assert client.project_id_resolver.is_disabled
