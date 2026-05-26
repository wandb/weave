"""Tests for ClickHouse batching behavior in the trace server.

This module verifies that multiple calls are properly batched into a single
ClickHouse insert operation for performance optimization.
"""

import base64
import datetime
import json
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.trace.util import client_is_sqlite
from weave.shared.digest import compute_file_digest, str_digest
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.base64_content_conversion import AUTO_CONVERSION_MIN_SIZE
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.errors import (
    InvalidRequest,
    ObjectDeletedError,
    handle_server_exception,
)
from weave.trace_server.file_storage import (
    FileStorageWriteError,
    key_for_project_digest,
)
from weave.trace_server.file_storage_uris import GCSFileStorageURI
from weave.trace_server.validation_util import CHValidationError
from weave.type_wrappers.Content.content import Content


def make_base_64_content(content: str) -> str:
    """Helper function to create base64 encoded content.

    Args:
        content (str): The content to encode.

    Returns:
        str: Base64 encoded content with data URI prefix.
    """
    return "data:text/plain;base64," + base64.b64encode(content.encode()).decode()


string_suffix = "a" * AUTO_CONVERSION_MIN_SIZE


def create_file_sized_content(content: str) -> str:
    """Create base64 content padded to exceed AUTO_CONVERSION_MIN_SIZE.

    This ensures the content is large enough to trigger file-based storage
    in ClickHouse rather than inline storage.
    """
    return make_base_64_content(content + string_suffix)


def _make_batch_req_with_contents(project_id: str, contents: list[str]):
    """Helper to build a CallCreateBatchReq where each call has one base64 input."""
    return tsi.CallCreateBatchReq(
        batch=[
            tsi.CallBatchStartMode(
                mode="start",
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        op_name=f"test_op_{i}",
                        started_at=datetime.datetime.now(datetime.timezone.utc),
                        attributes={},
                        inputs={"input": create_file_sized_content(c)},
                    )
                ),
            )
            for i, c in enumerate(contents)
        ]
    )


def test_clickhouse_batching():
    """Test that batched calls are properly sent to ClickHouse with correct parameters."""
    # Create a mock ClickHouse client
    mock_ch_client = MagicMock()

    # Mock the command method to avoid actual database operations
    mock_ch_client.command.return_value = None

    # Mock the insert method to track calls
    mock_ch_client.insert.return_value = MagicMock()
    # MagicMock is truthy, so get_project_data_residence() returns BOTH, which is incorrect, mock it
    mock_ch_client.query.return_value.result_rows = []

    # Create a ClickHouseTraceServer instance and patch _mint_client
    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")

        # Use properly base64 encoded project_id (entity/project format)
        project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

        # Simulate a legacy project by returning merged-only residence.
        mock_query_result = MagicMock()
        mock_query_result.result_rows = [[0, 1]]  # has_complete=0, has_merged=1
        mock_ch_client.query.return_value = mock_query_result

        # Create a batch of call start requests
        batch_req = tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_1",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": create_file_sized_content(
                                    "SOME BASE64 CONTENT - 1"
                                )
                            },
                        )
                    ),
                ),
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_2",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": create_file_sized_content(
                                    "SOME BASE64 CONTENT - 2"
                                )
                            },
                        )
                    ),
                ),
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="test_op_3",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={
                                "input": create_file_sized_content(
                                    "SOME BASE64 CONTENT - 3"
                                )
                            },
                        )
                    ),
                ),
            ]
        )

        # Execute the batch
        trace_server.call_start_batch(batch_req)

        # THE KEY ASSERTION:
        # Verify that there are exactly 2 inserts:
        # 1 for files and 1 for call_parts (order may vary)
        insert_call_count = mock_ch_client.insert.call_count
        assert insert_call_count == 2, (
            f"Expected exactly 2 ClickHouse insert calls for 3 batched calls "
            f"(and 3 base64 content objects, which are stored in files), "
            f"but got {insert_call_count} insert calls"
        )

        # Check that both files and call_parts were inserted (order may vary)
        insert_tables = [
            mock_ch_client.insert.call_args_list[0][0][0],
            mock_ch_client.insert.call_args_list[1][0][0],
        ]
        assert set(insert_tables) == {"files", "call_parts"}, (
            f"Expected inserts to files and call_parts tables, "
            f"but got inserts to: {insert_tables}"
        )


def test_clickhouse_batching_deduplicates_identical_files():
    """Duplicate content in the same batch should only produce one file insert."""
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()
    mock_ch_client.query.return_value.result_rows = []

    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")
        project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

        mock_query_result = MagicMock()
        mock_query_result.result_rows = [[0, 1]]
        mock_ch_client.query.return_value = mock_query_result

        # 3 calls with the SAME content
        same_content = "IDENTICAL CONTENT"
        batch_req = _make_batch_req_with_contents(
            project_id, [same_content, same_content, same_content]
        )
        trace_server.call_start_batch(batch_req)

        insert_tables = [call[0][0] for call in mock_ch_client.insert.call_args_list]
        assert set(insert_tables) == {"files", "call_parts"}

        # The files insert should contain chunks for only 1 unique file
        # (content + metadata), not 3 copies.
        files_insert = next(
            call
            for call in mock_ch_client.insert.call_args_list
            if call[0][0] == "files"
        )
        file_rows = files_insert[1]["data"]
        # Each Content object produces 2 files (content + metadata.json).
        # With dedup, 3 identical calls should still yield only 2 file rows.
        assert len(file_rows) == 2, (
            f"Expected 2 file rows (1 content + 1 metadata) for deduplicated batch, "
            f"got {len(file_rows)}"
        )


def _mk_obj(project_id: str, object_id: str, wb_user_id: str, val: dict[str, Any]):
    return tsi.ObjSchemaForInsert(
        project_id=project_id,
        object_id=object_id,
        wb_user_id=wb_user_id,
        val=val,
    )


def _internal_pid() -> str:
    # Any base64 string is valid for internal project id validation
    # Reuse the same value as other tests in this module
    return base64.b64encode(b"test_project").decode()


def _internal_wb_user_id() -> str:
    return base64.b64encode(b"test_user").decode()


def test_obj_batch_same_object_id_different_hash(trace_server, client):
    """Two versions for same object_id with different digests."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "my_obj"
    v1 = {"k": 1}
    v2 = {"k": 2}

    server.obj_create_batch(
        batch=[
            _mk_obj(pid, obj_id, wb_user_id, v1),
            _mk_obj(pid, obj_id, wb_user_id, v2),
        ]
    )

    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    digests = {o.digest for o in res.objs}
    assert digests == {str_digest(json.dumps(v1)), str_digest(json.dumps(v2))}
    # Exactly one latest
    assert sum(o.is_latest for o in res.objs) == 1


def test_obj_batch_same_hash_different_object_ids(trace_server, client):
    """Same digest payload uploaded under different object_ids yields distinct objects."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    val = {"shared": True}
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, "obj_1", wb_user_id, val),
            _mk_obj(pid, "obj_2", wb_user_id, val),
        ]
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(
                object_ids=["obj_1", "obj_2"], latest_only=False
            ),
        )
    )
    assert len(res.objs) == 2
    assert {o.object_id for o in res.objs} == {"obj_1", "obj_2"}


def test_obj_batch_identical_same_id_same_hash_deduplicates(trace_server, client):
    """Duplicate rows (same object_id and digest) are represented once in metadata view."""
    server = trace_server._internal_trace_server
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "dup_obj"
    val = {"x": 1}
    server.obj_create_batch(
        batch=[
            _mk_obj(pid, obj_id, wb_user_id, val),
            _mk_obj(pid, obj_id, wb_user_id, val),
        ]
    )
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 1
    assert res.objs[0].digest == str_digest(json.dumps(val))


def test_obj_batch_four_versions_and_read_path(trace_server, client):
    """Batch upload 4 versions and verify reads over all and latest work."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "multi_v"
    vals = [{"i": i} for i in range(4)]
    digests = [str_digest(json.dumps(v)) for v in vals]
    server.obj_create_batch(batch=[_mk_obj(pid, obj_id, wb_user_id, v) for v in vals])

    # All versions are queryable
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 4
    assert {o.digest for o in res.objs} == set(digests)
    assert sum(o.is_latest for o in res.objs) == 1

    # Each digest can be read specifically
    for d, v in zip(digests, vals, strict=False):
        read = server.obj_read(
            tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest=d)
        )
        assert read.obj.val == v

    # Latest alias reads the most recent version
    latest = server.obj_read(
        tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest="latest")
    )
    assert latest.obj.digest in set(digests)
    assert latest.obj.is_latest == 1


def test_obj_batch_delete_version_preserves_indices(trace_server, client):
    """Delete one version and ensure indices remain intact and deletion is reflected."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "del_v"
    vals = [{"i": i} for i in range(3)]
    delete_idx = 1

    server.obj_create_batch(batch=[_mk_obj(pid, obj_id, wb_user_id, v) for v in vals])
    # Remaining versions are intact; indices are not renumbered in metadata
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    pre_del_digests = [obj.digest for obj in res.objs]

    # Delete the middle version
    del_digest = pre_del_digests[delete_idx]

    server.obj_delete(
        tsi.ObjDeleteReq(project_id=pid, object_id=obj_id, digests=[del_digest])
    )

    # Reading deleted digest raises ObjectDeletedError
    with pytest.raises(ObjectDeletedError):
        server.obj_read(
            tsi.ObjReadReq(project_id=pid, object_id=obj_id, digest=del_digest)
        )

    # Remaining versions are intact; indices are not renumbered in metadata
    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    assert len(res.objs) == 2
    assert {obj.digest for obj in res.objs} == {pre_del_digests[0], pre_del_digests[2]}


def test_str_digest_is_key_order_independent():
    """str_digest must return the same value regardless of dict key insertion order."""
    val_a = {"b": 1, "a": 2, "c": [{"z": 9, "y": 8}]}
    val_b = {"a": 2, "c": [{"y": 8, "z": 9}], "b": 1}

    digest_a = str_digest(json.dumps(val_a, sort_keys=True))
    digest_b = str_digest(json.dumps(val_b, sort_keys=True))
    assert digest_a == digest_b

    # Without sort_keys the digests would differ
    assert str_digest(json.dumps(val_a)) != str_digest(json.dumps(val_b))


def test_obj_batch_different_key_order_deduplicates(trace_server, client):
    """Objects with identical values but different key ordering share the same digest."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    obj_id = "key_order_obj"

    val_a = {"b": 1, "a": 2}
    val_b = {"a": 2, "b": 1}

    server.obj_create_batch(
        batch=[
            _mk_obj(pid, obj_id, wb_user_id, val_a),
            _mk_obj(pid, obj_id, wb_user_id, val_b),
        ]
    )

    res = server.objs_query(
        tsi.ObjQueryReq(
            project_id=pid,
            filter=tsi.ObjectVersionFilter(object_ids=[obj_id], latest_only=False),
        )
    )
    # Both values are logically identical, so only one version should exist
    assert len(res.objs) == 1


def test_table_create_different_key_order_same_digest(trace_server):
    """Rows with different key ordering produce the same digest in table_create."""
    server = trace_server._internal_trace_server
    pid = _internal_pid()

    row_a = {"b": 1, "a": 2}
    row_b = {"a": 2, "b": 1}

    res = server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                project_id=pid,
                rows=[row_a, row_b],
            )
        )
    )

    # Both rows are logically identical so their digests must match
    assert len(res.row_digests) == 2
    assert res.row_digests[0] == res.row_digests[1]


def test_call_start_batch_invalid_trace_id_returns_400():
    """An invalid trace_id in a batch should fail the whole batch with a 400, not a 500.

    Regression test for: POST /call/upsert_batch drops entire batch for
    non-UUID trace_id (e.g. 'session:main:agent:main:main') with a 500
    instead of returning a useful validation error.
    """
    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()

    project_id = base64.b64encode(b"test_entity/test_project").decode("utf-8")

    mock_query_result = MagicMock()
    mock_query_result.result_rows = [[0, 1]]  # has_complete=0, has_merged=1

    with patch.object(
        ClickHouseTraceServer, "_mint_client", return_value=mock_ch_client
    ):
        trace_server = ClickHouseTraceServer(host="test_host")
        mock_ch_client.query.return_value = mock_query_result

        batch_req = tsi.CallCreateBatchReq(
            batch=[
                tsi.CallBatchStartMode(
                    mode="start",
                    req=tsi.CallStartReq(
                        start=tsi.StartedCallSchemaForInsert(
                            project_id=project_id,
                            op_name="invalid_op",
                            trace_id="session:main:agent:main:main",
                            started_at=datetime.datetime.now(datetime.timezone.utc),
                            attributes={},
                            inputs={},
                        )
                    ),
                ),
            ]
        )

        # The batch should raise CHValidationError, not an opaque internal error
        with pytest.raises(CHValidationError, match="Invalid UUID"):
            trace_server.call_start_batch(batch_req)

        # The error registry should map CHValidationError to 400 (not 500)
        try:
            trace_server.call_start_batch(batch_req)
        except CHValidationError as e:
            error_with_status = handle_server_exception(e)
            assert error_with_status.status_code == 400
            assert "Invalid UUID" in error_with_status.message["reason"]


def test_obj_batch_mixed_projects_errors(trace_server, client):
    """Uploading objects to different projects in one batch should error."""
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support batch object creation")
    server = trace_server._internal_trace_server
    pid1 = _internal_pid()
    wb_user_id = _internal_wb_user_id()
    pid2 = "cHJvamVjdF8y"  # base64("project_2")
    batch = [
        _mk_obj(pid1, "p1_obj", wb_user_id, {"a": 1}),
        _mk_obj(pid2, "p2_obj", wb_user_id, {"b": 2}),
    ]

    with pytest.raises(
        InvalidRequest,
        match="obj_create_batch only supports updating a single project.",
    ):
        server.obj_create_batch(batch=batch)


# ---------------------------------------------------------------------------
# Parallel bucket-upload fan-out (call_batch + bucket-backed file storage)
# ---------------------------------------------------------------------------
#
# These exercise the full call_start_batch -> file_create -> bucket-flush path
# in ClickHouseTraceServer with the bucket allow-list enabled. The CH client
# is a MagicMock that records inserts (same pattern as test_clickhouse_batching
# above); the bucket uploader is patched at both call sites with a recording
# stand-in that tracks concurrency and can inject per-file failures.


class _RecordingUploader:
    """Drop-in replacement for `store_in_bucket`. Records calls, tracks
    concurrent peak, can inject per-path failures, and supports a per-call
    delay to make parallelism observable in wall time.
    """

    def __init__(
        self,
        *,
        delay: float = 0.0,
        fail_paths: set[str] | None = None,
    ) -> None:
        self.delay = delay
        self.fail_paths = fail_paths or set()
        self.calls: list[tuple[str, bytes]] = []
        self.concurrent_peak = 0
        self._inflight = 0
        self._lock = threading.Lock()

    def __call__(self, client, path, data):
        with self._lock:
            self._inflight += 1
            self.concurrent_peak = max(self.concurrent_peak, self._inflight)
        try:
            if path in self.fail_paths:
                raise FileStorageWriteError(f"injected failure for {path}")
            if self.delay:
                time.sleep(self.delay)
            with self._lock:
                self.calls.append((path, data))
        finally:
            with self._lock:
                self._inflight -= 1
        return GCSFileStorageURI("test-bucket", path)


def _bucket_backed_trace_server(monkeypatch, uploader: _RecordingUploader):
    """Spin up a ClickHouseTraceServer wired to a recording mock CH client and
    a patched bucket uploader. Returns (server, mock_ch_client).

    `_mint_client` is patched for the lifetime of the test via monkeypatch so
    every thread-local first-use of `ch_client` resolves to the recording
    mock, including inside ThreadPoolExecutor workers spawned by the parallel
    bucket flush.
    """
    # Force the bucket write path for every project.
    monkeypatch.setenv("WF_FILE_STORAGE_PROJECT_ALLOW_LIST", "*")
    # Patch the actual upload at both call sites (sync + deferred).
    monkeypatch.setattr(
        "weave.trace_server.clickhouse_trace_server_batched.store_in_bucket",
        uploader,
    )
    monkeypatch.setattr(
        "weave.trace_server.parallel_bucket_uploads.store_in_bucket",
        uploader,
    )

    mock_ch_client = MagicMock()
    mock_ch_client.command.return_value = None
    mock_ch_client.insert.return_value = MagicMock()
    # Force the legacy-residence branch (call_parts).
    query_result = MagicMock()
    query_result.result_rows = [[0, 1]]
    mock_ch_client.query.return_value = query_result

    monkeypatch.setattr(
        ClickHouseTraceServer, "_mint_client", lambda self: mock_ch_client
    )
    server = ClickHouseTraceServer(host="test_host")
    # Inject a non-None storage client so the bucket branch fires; the actual
    # client is opaque since the uploader is patched.
    server._file_storage_client = MagicMock()
    server._file_storage_client_initialized = True
    return server, mock_ch_client


def _files_insert(mock_ch_client) -> list:
    """Pull the chunk rows from the recorded `files` insert call."""
    for call in mock_ch_client.insert.call_args_list:
        if call[0][0] == "files":
            return call[1]["data"]
    raise AssertionError("no `files` insert recorded")


def _batch_with_inputs(project_id: str, inputs: list[str]) -> tsi.CallCreateBatchReq:
    """N call_start items, each with one base64 input that triggers file_create."""
    return tsi.CallCreateBatchReq(
        batch=[
            tsi.CallBatchStartMode(
                mode="start",
                req=tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        op_name=f"op_{i}",
                        started_at=datetime.datetime.now(datetime.timezone.utc),
                        attributes={},
                        inputs={"v": content},
                    )
                ),
            )
            for i, content in enumerate(inputs)
        ]
    )


@pytest.mark.disable_logging_error_check
def test_call_start_batch_uploads_files_to_bucket_in_parallel_and_dedupes(monkeypatch):
    """Across a single call_start_batch we expect:

    * bucket uploads run in parallel (concurrent peak > 1, wall time well
      under the serial bound),
    * every chunk row in the `files` insert carries a `gs://` URI and an
      empty inline payload (i.e. nothing fell back to CH chunks),
    * identical content shared across calls dedups to a single upload + one
      pair of chunk rows (content + metadata.json),
    * the `call_parts` insert still receives one row per call in the batch.
    """
    uploader = _RecordingUploader(delay=0.1)
    server, mock_ch_client = _bucket_backed_trace_server(monkeypatch, uploader)

    project_id = base64.b64encode(b"u/p_parallel").decode()
    # 4 unique + 2 duplicates of the first one => 4 unique blobs, 5 distinct
    # call rows. Each blob produces 2 GCS objects (content + metadata.json),
    # so we expect 4 * 2 = 8 uploads, not 6 * 2 = 12.
    inputs = [
        create_file_sized_content("alpha"),
        create_file_sized_content("beta"),
        create_file_sized_content("gamma"),
        create_file_sized_content("delta"),
        create_file_sized_content("alpha"),  # dup
        create_file_sized_content("alpha"),  # dup
    ]
    start = time.monotonic()
    server.call_start_batch(_batch_with_inputs(project_id, inputs))
    elapsed = time.monotonic() - start

    # Parallelism: 8 uploads * 100ms = 800ms serial bound; should land well
    # below that with the default 8-wide pool. Allow generous slack for CI.
    assert uploader.concurrent_peak >= 2, (
        f"expected concurrent uploads, peak={uploader.concurrent_peak}"
    )
    assert elapsed < 0.5, f"flush was effectively serial: {elapsed:.3f}s"

    # Dedup at the upload layer: identical content collapses to one upload.
    upload_paths = [path for path, _ in uploader.calls]
    assert len(upload_paths) == len(set(upload_paths)), (
        f"duplicate uploads slipped past dedup: {upload_paths}"
    )
    assert len(uploader.calls) == 8  # 4 unique blobs * 2 GCS objects each

    # `files` insert: same dedup story, every row points at the bucket.
    file_rows = _files_insert(mock_ch_client)
    assert len(file_rows) == 8
    # Column order is sorted(FileChunkCreateCHInsertable.model_fields):
    # 0:bytes_stored 1:chunk_index 2:digest 3:file_storage_uri
    # 4:n_chunks 5:name 6:project_id 7:val_bytes
    for row in file_rows:
        assert isinstance(row[3], str)
        assert row[3].startswith("gs://test-bucket/")
        assert row[7] == b""  # bucket rows carry no inline bytes

    # `call_parts`: one row per call in the original batch (no dedup there).
    call_parts = next(
        call[1]["data"]
        for call in mock_ch_client.insert.call_args_list
        if call[0][0] == "call_parts"
    )
    assert len(call_parts) == len(inputs)


@pytest.mark.disable_logging_error_check
def test_call_start_batch_falls_back_to_clickhouse_on_per_file_bucket_failure(
    monkeypatch,
):
    """A FileStorageWriteError on one upload must not poison the rest of the
    batch. The failing file lands as inline ClickHouse chunks; the others keep
    their bucket URIs; every call in the batch still completes.
    """
    # Build a payload larger than FILE_CHUNK_SIZE so the CH fallback actually
    # chunks (and we can assert chunk_index / n_chunks behavior end-to-end).
    big_body = "fail-me-" + ("z" * (ch_settings.FILE_CHUNK_SIZE + AUTO_CONVERSION_MIN_SIZE))
    small_body = "ok-content"

    project_id = base64.b64encode(b"u/p_fallback").decode()
    big_content = Content.from_data_url(create_file_sized_content(big_body)).data
    big_digest = compute_file_digest(big_content)
    fail_path = key_for_project_digest(project_id, big_digest)

    uploader = _RecordingUploader(fail_paths={fail_path})
    server, mock_ch_client = _bucket_backed_trace_server(monkeypatch, uploader)

    inputs = [
        create_file_sized_content(small_body),
        create_file_sized_content(big_body),  # this one fails to upload
    ]
    server.call_start_batch(_batch_with_inputs(project_id, inputs))

    file_rows = _files_insert(mock_ch_client)
    # Column order is sorted(FileChunkCreateCHInsertable.model_fields):
    # 0:bytes_stored 1:chunk_index 2:digest 3:file_storage_uri
    # 4:n_chunks 5:name 6:project_id 7:val_bytes
    bucket_rows = [r for r in file_rows if r[3] is not None]
    ch_fallback_rows = [r for r in file_rows if r[3] is None]
    assert bucket_rows, "expected at least one row from the successful upload"
    assert ch_fallback_rows, "expected fallback rows for the failed upload"
    for row in bucket_rows:
        assert isinstance(row[3], str)
        assert row[3].startswith("gs://test-bucket/")
        assert row[7] == b""  # no inline bytes for bucket rows

    # Reassembling the fallback rows by chunk_index must yield the original
    # content (this is the contract the CH read path relies on).
    digest_to_chunks: dict[str, list[tuple[int, bytes]]] = {}
    for row in ch_fallback_rows:
        digest_to_chunks.setdefault(row[2], []).append((row[1], row[7]))
    assert big_digest in digest_to_chunks, (
        f"failed-upload digest {big_digest} not present in fallback rows"
    )
    chunks = sorted(digest_to_chunks[big_digest])
    reassembled = b"".join(chunk for _, chunk in chunks)
    assert reassembled == big_content
    assert [i for i, _ in chunks] == list(range(len(chunks)))

    # And the rest of the batch still landed in call_parts: 2 call rows.
    call_parts = next(
        call[1]["data"]
        for call in mock_ch_client.insert.call_args_list
        if call[0][0] == "call_parts"
    )
    assert len(call_parts) == 2


def test_serial_file_create_outside_call_batch_uploads_synchronously(monkeypatch):
    """Non-batch `file_create` calls must keep going through the synchronous
    bucket path (no defer, no thread pool). This is the regression guard for
    everything that calls file_create outside of call_batch — obj_create_batch,
    table writes, ad-hoc file_create endpoints, etc.
    """
    uploader = _RecordingUploader()
    server, mock_ch_client = _bucket_backed_trace_server(monkeypatch, uploader)

    project_id = base64.b64encode(b"u/p_serial").decode()
    payload = b"some-file-bytes"
    res = server.file_create(
        tsi.FileCreateReq(project_id=project_id, name="thing.bin", content=payload)
    )

    # The upload ran inline: one call, no batched pool, peak concurrency 1.
    assert len(uploader.calls) == 1
    path, body = uploader.calls[0]
    assert body == payload
    assert path.endswith(res.digest)
    assert uploader.concurrent_peak == 1

    # And the file-chunk row was committed (synchronous insert path).
    file_rows = _files_insert(mock_ch_client)
    assert len(file_rows) == 1
    assert any(
        isinstance(v, str) and v.startswith("gs://test-bucket/") for v in file_rows[0]
    )
