"""Write-path tests for the managed-bucket export engine.

The job manifest is stored through the real file-storage implementation before
the detached ClickHouse inserts begin. The local test ClickHouse intentionally
has no production named collection, so the native inserts finish as errors in
``system.query_log`` rather than writing production-like artifacts.
"""

import json
import time
import uuid
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws

from tests.trace.server_utils import find_server_layer
from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import export
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.export_targets import (
    build_feedback_export_query,
)
from weave.trace_server.file_storage import S3StorageClient
from weave.trace_server.file_storage_credentials import AWSCredentials
from weave.trace_server.file_storage_uris import S3FileStorageURI
from weave.trace_server.project_version.types import ReadTable

pytestmark = pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: export write path"
)

QUERY_LOG_POLL_SECONDS = 20
BUCKET = "weave-export-write-path"


@pytest.fixture
def storage_client():
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        credentials: AWSCredentials = {
            "access_key_id": "test-key",
            "secret_access_key": "test-secret",
            "session_token": None,
            "region": "us-east-1",
            "kms_key": None,
        }
        yield S3StorageClient(
            S3FileStorageURI.parse_uri_str(f"s3://{BUCKET}"), credentials
        )


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """Unwrap the internal ClickHouse server from the external fixture."""
    return find_server_layer(trace_server, ClickHouseTraceServer)


def test_build_export_insert_sql_exact_string():
    sql = export.build_export_insert_sql(
        export.ResolvedExportTarget("feedback", build_feedback_export_query()),
        "exports/proj/job/feedback/data.parquet",
    )
    # Complete-string equality: the collection appears by name only, so the
    # ch-writer credential can never leak into SQL or query_log.
    assert sql == (
        "INSERT INTO FUNCTION s3(weave_exports, "
        "filename = 'exports/proj/job/feedback/data.parquet', format = 'Parquet') "
        "SELECT * FROM feedback WHERE project_id = {project_id:String}"
    )


def test_start_export_runs_targets_serially_in_one_worker(
    monkeypatch: pytest.MonkeyPatch,
    storage_client: S3StorageClient,
):
    worker_starts: list[tuple[object, tuple[object, ...], bool]] = []

    class _ImmediateThread:
        def __init__(self, *, target, args, daemon):
            worker_starts.append((target, args, daemon))

        def start(self):
            target, args, _ = worker_starts[-1]
            target(*args)

    export_client = MagicMock()
    command_query_ids: list[str] = []

    def _command(_sql, *, parameters, settings):
        assert parameters == {"project_id": "project"}
        command_query_ids.append(settings["query_id"])
        if len(command_query_ids) == 1:
            raise RuntimeError("first target failed")

    export_client.command.side_effect = _command
    mint_client = MagicMock(return_value=export_client)
    count_client = MagicMock()
    count_client.query.return_value.result_rows = [(0,)]
    monkeypatch.setattr(export.threading, "Thread", _ImmediateThread)

    job_id = export.start_export(
        count_client,
        mint_client,
        storage_client,
        "project",
        ["objects", "feedback"],
        ReadTable.CALLS_COMPLETE,
    )

    assert len(worker_starts) == 1
    assert worker_starts[0][2] is True
    assert mint_client.call_count == 1
    assert command_query_ids == [f"{job_id}:objects", f"{job_id}:feedback"]
    manifest = json.loads(
        storage_client.read(
            storage_client.base_uri.with_path(
                export.export_job_prefix("project", job_id) + "manifest.json"
            )
        )
    )
    assert manifest["job_id"] == job_id
    assert [target["target"] for target in manifest["targets"]] == [
        "objects",
        "feedback",
    ]


def test_export_start_writes_manifest_without_creating_a_clickhouse_table(
    clickhouse_trace_server, storage_client: S3StorageClient
):
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    project_id = b64(f"{TEST_ENTITY}/export-write-path")
    res = clickhouse_trace_server.export_start(
        tsi.ExportStartReq(project_id=project_id, targets=["objects", "feedback"])
    )
    assert export.JOB_ID_RE.match(res.job_id)
    assert clickhouse_trace_server.ch_client.query(
        "EXISTS TABLE export_jobs"
    ).result_rows == [(0,)]
    manifest = json.loads(
        storage_client.read(
            storage_client.base_uri.with_path(
                export.export_job_prefix(project_id, res.job_id) + "manifest.json"
            )
        )
    )
    assert manifest["job_id"] == res.job_id
    assert [target["target"] for target in manifest["targets"]] == [
        "objects",
        "feedback",
    ]


def test_export_start_query_id_lands_in_query_log(
    clickhouse_trace_server, storage_client: S3StorageClient
):
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    project_id = b64(f"{TEST_ENTITY}/export-query-log")
    res = clickhouse_trace_server.export_start(
        tsi.ExportStartReq(project_id=project_id, targets=["objects"])
    )
    qid = f"{res.job_id}:objects"
    ch = clickhouse_trace_server.ch_client
    deadline = time.monotonic() + QUERY_LOG_POLL_SECONDS
    rows: list[tuple[str]] = []
    while time.monotonic() < deadline:
        ch.command("SYSTEM FLUSH LOGS")
        rows = ch.query(
            "SELECT DISTINCT query_id FROM system.query_log "
            "WHERE query_id = {qid:String}",
            parameters={"qid": qid},
        ).result_rows
        if rows:
            break
        time.sleep(0.5)
    assert rows == [(qid,)]


def test_bad_target_and_job_id_validation(storage_client: S3StorageClient):
    with pytest.raises(export.ExportError) as exc_info:
        export.start_export(
            MagicMock(),
            MagicMock(),
            storage_client,
            "project",
            ["objects", "nope"],
            ReadTable.CALLS_COMPLETE,
        )
    assert exc_info.value.http_status == 400
    assert exc_info.value.code == "BAD_TARGET"
    assert export.JOB_ID_RE.match("not-a-uuid") is None
    assert export.JOB_ID_RE.match(str(uuid.uuid4()))
    assert export.export_object_prefix("p", "j", "calls") == "exports/p/j/calls/"


@pytest.mark.parametrize("targets", [[], ["objects", "objects"]])
def test_empty_and_duplicate_targets_are_rejected(
    storage_client: S3StorageClient, targets: list[str]
):
    with pytest.raises(export.ExportError) as exc_info:
        export.start_export(
            MagicMock(),
            MagicMock(),
            storage_client,
            "project",
            targets,
            ReadTable.CALLS_COMPLETE,
        )
    assert (exc_info.value.http_status, exc_info.value.code) == (400, "BAD_TARGET")
