"""Tests for the detached ClickHouse-to-S3 export write path."""

import datetime
import json
import time
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
    build_objects_export_query,
)
from weave.trace_server.file_storage import FileStorageWriteError, S3StorageClient
from weave.trace_server.file_storage_credentials import AWSCredentials
from weave.trace_server.file_storage_uris import S3FileStorageURI
from weave.trace_server.project_version.types import ReadTable

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


def test_start_export_persists_manifest_and_runs_targets_serially_in_one_worker(
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
    commands: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def _command(sql, *, parameters, settings):
        assert parameters == {"project_id": "project"}
        commands.append((sql, parameters, settings))
        if len(commands) == 1:
            raise RuntimeError("first target failed")

    export_client.command.side_effect = _command
    mint_client = MagicMock(return_value=export_client)
    monkeypatch.setattr(export.threading, "Thread", _ImmediateThread)

    job_id = export.start_export(
        mint_client,
        storage_client,
        "project",
        ["objects", "feedback"],
        ReadTable.CALLS_COMPLETE,
    )

    assert len(worker_starts) == 1
    assert worker_starts[0][2] is True
    assert mint_client.call_count == 1
    assert [command[2]["query_id"] for command in commands] == [
        f"{job_id}:objects",
        f"{job_id}:feedback",
    ]
    assert [command[0] for command in commands] == [
        (
            "INSERT INTO FUNCTION s3(weave_exports, "
            f"filename = 'exports/project/{job_id}/objects/data.parquet', "
            "format = 'Parquet') "
            f"{build_objects_export_query()}"
        ),
        (
            "INSERT INTO FUNCTION s3(weave_exports, "
            f"filename = 'exports/project/{job_id}/feedback/data.parquet', "
            "format = 'Parquet') "
            f"{build_feedback_export_query()}"
        ),
    ]
    manifest = json.loads(
        storage_client.read(
            storage_client.base_uri.with_path(
                export.export_job_prefix("project", job_id) + "manifest.json"
            )
        )
    )
    created_at = datetime.datetime.fromisoformat(manifest.pop("created_at"))
    assert created_at.tzinfo == datetime.timezone.utc
    assert manifest == {
        "job_id": job_id,
        "format": "parquet",
        "targets": [
            {"target": "objects", "object": "objects/data.parquet"},
            {"target": "feedback", "object": "feedback/data.parquet"},
        ],
    }


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: export server entry point"
)
def test_export_start_persists_manifest(
    clickhouse_trace_server, storage_client: S3StorageClient
):
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    project_id = b64(f"{TEST_ENTITY}/export-write-path")
    res = clickhouse_trace_server.export_start(
        tsi.ExportStartReq(project_id=project_id, targets=["objects", "feedback"])
    )
    assert export.JOB_ID_RE.match(res.job_id)
    manifest = json.loads(
        storage_client.read(
            storage_client.base_uri.with_path(
                export.export_job_prefix(project_id, res.job_id) + "manifest.json"
            )
        )
    )
    created_at = datetime.datetime.fromisoformat(manifest.pop("created_at"))
    assert created_at.tzinfo == datetime.timezone.utc
    assert manifest == {
        "job_id": res.job_id,
        "format": "parquet",
        "targets": [
            {"target": "objects", "object": "objects/data.parquet"},
            {"target": "feedback", "object": "feedback/data.parquet"},
        ],
    }


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: query_log verification"
)
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


def test_start_export_requires_durable_manifest(
    monkeypatch: pytest.MonkeyPatch,
):
    mint_client = MagicMock()
    with pytest.raises(export.ExportError) as exc_info:
        export.start_export(
            mint_client,
            None,
            "project",
            ["objects"],
            ReadTable.CALLS_COMPLETE,
        )
    assert (exc_info.value.http_status, exc_info.value.code) == (
        503,
        "EXPORT_STORAGE_UNAVAILABLE",
    )

    failed_write = MagicMock(side_effect=FileStorageWriteError())
    monkeypatch.setattr(export, "store_in_bucket", failed_write)
    with pytest.raises(export.ExportError) as exc_info:
        export.start_export(
            mint_client,
            MagicMock(),
            "project",
            ["objects"],
            ReadTable.CALLS_COMPLETE,
        )
    assert (exc_info.value.http_status, exc_info.value.code) == (
        503,
        "EXPORT_STORAGE_UNAVAILABLE",
    )
    failed_write.assert_called_once()
    assert mint_client.call_count == 0


def test_start_export_rejects_invalid_targets_before_writing(
    monkeypatch: pytest.MonkeyPatch,
):
    store = MagicMock()
    monkeypatch.setattr(export, "store_in_bucket", store)
    for targets in ([], ["objects", "objects"], ["objects", "nope"]):
        mint_client = MagicMock()
        with pytest.raises(export.ExportError) as exc_info:
            export.start_export(
                mint_client,
                MagicMock(),
                "project",
                targets,
                ReadTable.CALLS_COMPLETE,
            )
        assert (exc_info.value.http_status, exc_info.value.code) == (
            400,
            "BAD_TARGET",
        )
        assert mint_client.call_count == 0
    store.assert_not_called()
