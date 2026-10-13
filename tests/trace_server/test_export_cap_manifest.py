"""Functional whale-cap + manifest tests for the export write path."""

import json
import uuid

import boto3
import pytest
from moto import mock_aws

from tests.trace.server_utils import find_server_layer
from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from tests.trace_server.test_export_targets import _make_completed_call
from weave.trace_server import export
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.file_storage import S3StorageClient
from weave.trace_server.file_storage_credentials import AWSCredentials
from weave.trace_server.file_storage_uris import S3FileStorageURI
from weave.trace_server.project_version.types import CallsStorageServerMode

pytestmark = pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: export cap + manifest"
)

BUCKET = "weave-export-cap-manifest"


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """Return the internal ClickHouse server and enforce AUTO routing mode."""
    internal_server = find_server_layer(trace_server, ClickHouseTraceServer)
    internal_server.table_routing_resolver._mode = CallsStorageServerMode.AUTO
    return internal_server


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


def test_cap_trips_fail_closed(
    trace_server, clickhouse_trace_server, storage_client: S3StorageClient, monkeypatch
):
    """Over-cap precount raises 409 TOO_LARGE and writes nothing durable."""
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    project = f"{TEST_ENTITY}/export_cap_trips"
    internal = b64(project)
    _insert_calls(trace_server, project, 3)
    monkeypatch.setenv("WF_EXPORT_MAX_ROWS", "2")
    with pytest.raises(export.ExportError) as exc_info:
        clickhouse_trace_server.export_start(
            tsi.ExportStartReq(project_id=internal, targets=["calls"])
        )
    assert exc_info.value.http_status == 409
    assert exc_info.value.code == "TOO_LARGE"
    assert str(exc_info.value) == "target 'calls' has 3 rows > cap 2"
    assert storage_client.client.list_objects_v2(Bucket=BUCKET).get("Contents") is None
    assert clickhouse_trace_server.ch_client.query(
        "EXISTS TABLE export_jobs"
    ).result_rows == [(0,)]


def test_cap_allows_and_writes_manifest(
    trace_server,
    clickhouse_trace_server,
    storage_client: S3StorageClient,
    monkeypatch,
):
    """Under-cap export persists its complete manifest before detached work starts."""
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    project = f"{TEST_ENTITY}/export_cap_allows"
    internal = b64(project)
    _insert_calls(trace_server, project, 3)
    monkeypatch.setenv("WF_EXPORT_MAX_ROWS", "100")
    res = clickhouse_trace_server.export_start(
        tsi.ExportStartReq(project_id=internal, targets=["calls"])
    )
    assert export.JOB_ID_RE.match(res.job_id)
    manifest = json.loads(
        storage_client.read(
            storage_client.base_uri.with_path(
                export.export_job_prefix(internal, res.job_id) + "manifest.json"
            )
        )
    )
    assert manifest["job_id"] == res.job_id
    assert manifest["format"] == "parquet"
    assert manifest["targets"] == [
        {"target": "calls", "expected_rows": 3, "object": "calls/data.parquet"}
    ]


def test_manifest_builder_keeps_the_customer_facing_job_shape():
    manifest = json.loads(
        export.build_manifest_json("job-123", [("calls", 3), ("feedback", 1)])
    )
    assert manifest["job_id"] == "job-123"
    assert manifest["format"] == "parquet"
    assert manifest["targets"] == [
        {"target": "calls", "expected_rows": 3, "object": "calls/data.parquet"},
        {
            "target": "feedback",
            "expected_rows": 1,
            "object": "feedback/data.parquet",
        },
    ]
    assert export.export_job_prefix("p", "j") == "exports/p/j/"


def _insert_calls(trace_server, project_id: str, count: int) -> None:
    """Insert real completed calls through the public write path."""
    batch = [_make_completed_call(project_id, str(uuid.uuid4())) for _ in range(count)]
    trace_server.calls_complete(tsi.CallsUpsertCompleteReq(batch=batch))
