"""Functional status-path tests for the managed-bucket export engine.

Real ClickHouse provides the ``system.query_log`` oracle and moto exercises
the real S3 storage client for the durable manifest, artifact, and presign
paths. No job table or in-memory job registry participates in this flow.
"""

import time
import uuid

import boto3
import pytest
import requests
from clickhouse_connect.driver.client import Client as CHClient
from clickhouse_connect.driver.exceptions import DatabaseError
from moto import mock_aws

from tests.trace.server_utils import find_server_layer
from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest import TEST_ENTITY
from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import export
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.file_storage import S3StorageClient
from weave.trace_server.file_storage_credentials import AWSCredentials
from weave.trace_server.file_storage_uris import S3FileStorageURI

pytestmark = pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND, reason="ClickHouse-only: export status via query_log"
)

ORACLE_DEADLINE_SECONDS = 20
SCRATCH_TABLE = "export_status_scratch"
BUCKET = "weave-exports"


@pytest.fixture
def clickhouse_trace_server(trace_server):
    """Unwrap the internal ClickHouse server from the external fixture."""
    return find_server_layer(trace_server, ClickHouseTraceServer)


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


def test_poll_query_status_oracle_against_real_query_log(clickhouse_trace_server):
    ch = clickhouse_trace_server.ch_client
    _make_scratch_table(ch)

    done_qid = f"{uuid.uuid4()}:objects"
    ch.command(
        f"INSERT INTO {SCRATCH_TABLE} SELECT number FROM numbers(7)",
        settings={"query_id": done_qid},
    )
    assert _poll_until_terminal(ch, done_qid) == ("done", 7, None)

    error_qid = f"{uuid.uuid4()}:objects"
    with pytest.raises(DatabaseError):
        ch.command(
            "SELECT throwIf(number = 0, 'boom') FROM numbers(1)",
            settings={"query_id": error_qid},
        )
    status, rows, error = _poll_until_terminal(ch, error_qid)
    assert (status, rows) == ("error", 0)
    assert error is not None
    assert "boom" in error

    assert export.poll_query_status(ch, f"{uuid.uuid4()}:objects") == (
        "running",
        0,
        None,
    )


def test_query_log_oracle_sql_supports_standalone_and_replica_clusters():
    assert export._flush_query_log_sql(None) == "SYSTEM FLUSH LOGS query_log"
    assert export._query_log_status_sql(None) == (
        "SELECT type, written_rows, exception FROM system.query_log "
        "WHERE query_id = {qid:String} AND event_date >= today() - 1 "
        "ORDER BY event_time_microseconds DESC LIMIT 1"
    )

    assert (
        export._flush_query_log_sql("default")
        == "SYSTEM FLUSH LOGS ON CLUSTER default query_log"
    )
    assert export._query_log_status_sql("default") == (
        "SELECT type, written_rows, exception FROM "
        "clusterAllReplicas('default', merge('system', '^query_log*')) "
        "WHERE query_id = {qid:String} AND event_date >= today() - 1 "
        "ORDER BY event_time_microseconds DESC LIMIT 1"
    )


def test_export_status_recovers_job_with_no_memory_state(
    clickhouse_trace_server, storage_client: S3StorageClient
):
    project_id = b64(f"{TEST_ENTITY}/export-status-recovery")
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    start_res = clickhouse_trace_server.export_start(
        tsi.ExportStartReq(project_id=project_id, targets=["objects", "feedback"])
    )
    # A brand-new server instance proves status is recovered from object storage
    # plus query_log, not a process-local map or a ClickHouse metadata table.
    fresh_server = ClickHouseTraceServer(
        host=clickhouse_trace_server._host,
        port=clickhouse_trace_server._port,
        user=clickhouse_trace_server._user,
        password=clickhouse_trace_server._password,
        database=clickhouse_trace_server._database,
    )
    fresh_server._file_storage_client = storage_client
    fresh_server._file_storage_client_initialized = True
    status_req = tsi.ExportStatusReq(project_id=project_id, job_id=start_res.job_id)
    deadline = time.monotonic() + ORACLE_DEADLINE_SECONDS
    status_res = fresh_server.export_status(status_req)
    # The detached inserts fail (no weave_exports collection in the test CH);
    # wait until both targets reach their terminal error in query_log.
    while time.monotonic() < deadline and any(
        entry.status != "error" for entry in status_res.manifest
    ):
        time.sleep(0.5)
        status_res = fresh_server.export_status(status_req)

    assert status_res.status == "error"
    assert [entry.target for entry in status_res.manifest] == ["objects", "feedback"]
    for entry in status_res.manifest:
        assert entry.status == "error"
        assert entry.error is not None
        assert entry.error != ""
        assert entry.rows == 0
        assert entry.objects == []
        assert entry.urls == []
        assert entry.expires_at is None


def test_cross_tenant_unknown_and_traversal_guards(
    clickhouse_trace_server, storage_client: S3StorageClient
):
    project_a = b64(f"{TEST_ENTITY}/export-status-tenant-a")
    project_b = b64(f"{TEST_ENTITY}/export-status-tenant-b")
    clickhouse_trace_server._file_storage_client = storage_client
    clickhouse_trace_server._file_storage_client_initialized = True
    start_res = clickhouse_trace_server.export_start(
        tsi.ExportStartReq(project_id=project_a, targets=["objects"])
    )

    with pytest.raises(export.ExportError) as cross_tenant:
        clickhouse_trace_server.export_status(
            tsi.ExportStatusReq(project_id=project_b, job_id=start_res.job_id)
        )
    assert (cross_tenant.value.http_status, cross_tenant.value.code) == (
        404,
        "NOT_FOUND",
    )

    with pytest.raises(export.ExportError) as unknown:
        clickhouse_trace_server.export_status(
            tsi.ExportStatusReq(project_id=project_a, job_id=str(uuid.uuid4()))
        )
    assert (unknown.value.http_status, unknown.value.code) == (404, "NOT_FOUND")

    with pytest.raises(export.ExportError) as traversal:
        clickhouse_trace_server.export_status(
            tsi.ExportStatusReq(project_id=project_a, job_id="../../etc/passwd")
        )
    assert (traversal.value.http_status, traversal.value.code) == (400, "BAD_JOB_ID")


def test_presign_on_done_downloads_exact_artifact(
    clickhouse_trace_server, storage_client: S3StorageClient
):
    ch = clickhouse_trace_server.ch_client
    project_id = b64(f"{TEST_ENTITY}/export-status-presign")
    job_id = str(uuid.uuid4())

    # Make the oracle report objects done via a real insert under the job's query_id.
    _make_scratch_table(ch)
    ch.command(
        f"INSERT INTO {SCRATCH_TABLE} SELECT number FROM numbers(5)",
        settings={"query_id": f"{job_id}:objects"},
    )
    assert _poll_until_terminal(ch, f"{job_id}:objects") == ("done", 5, None)

    storage_client.store(
        storage_client.base_uri.with_path(
            export.export_job_prefix(project_id, job_id) + "manifest.json"
        ),
        export.build_manifest_json(job_id, ["objects"]),
    )
    key = export.export_object_prefix(project_id, job_id, "objects") + "data.parquet"
    artifact = b"PAR1-status-artifact"
    storage_client.store(storage_client.base_uri.with_path(key), artifact)

    res = export.get_export_status(ch, storage_client, project_id, job_id)
    assert res.status == "done"
    entry = res.manifest[0]
    assert (entry.target, entry.status, entry.rows) == ("objects", "done", 5)
    assert entry.objects == [key]
    assert len(entry.urls) == 1
    assert entry.expires_at is not None
    assert entry.error is None
    # Real read-only download over the presigned GET: no CH creds involved.
    assert requests.get(entry.urls[0], timeout=5).content == artifact


def _make_scratch_table(ch: CHClient) -> None:
    ch.command(
        f"CREATE TABLE IF NOT EXISTS {SCRATCH_TABLE} "
        "(n UInt64) ENGINE = MergeTree ORDER BY n"
    )


def _poll_until_terminal(
    ch: CHClient, query_id: str
) -> tuple[tsi.ExportJobStatus, int, str | None]:
    """FLUSH LOGS + poll the oracle until it leaves running (or times out)."""
    deadline = time.monotonic() + ORACLE_DEADLINE_SECONDS
    result: tuple[tsi.ExportJobStatus, int, str | None] = ("running", 0, None)
    while time.monotonic() < deadline:
        ch.command("SYSTEM FLUSH LOGS")
        result = export.poll_query_status(ch, query_id)
        if result[0] != "running":
            return result
        time.sleep(0.5)
    return result
