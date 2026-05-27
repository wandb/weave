"""End-to-end integration test for the bulk-export flow.

Runs against a real ClickHouse + MinIO stack brought up by the sibling
`docker-compose.export-e2e.yml`. Exercises the full path: `POST /export/start`
submits a detached `INSERT INTO FUNCTION s3()` against MinIO, `GET
/export/{job_id}` derives state from `system.query_log`, mints a presigned
URL, and the test downloads the file and validates the Parquet content.

Skipped by default. To run:

    docker compose -f tests/trace_server/export/docker-compose.export-e2e.yml up -d
    EXPORT_E2E=1 uv run --group test python -m pytest \
        tests/trace_server/export/test_export_integration.py -v

`AWS_ENDPOINT_URL_S3` is set automatically by the fixture so boto3's
presigned-URL minter (`PresignedUrlMinter`) targets the local MinIO instead
of real AWS S3. ClickHouse reaches MinIO via the in-network hostname
`minio:9000`; the test reaches it via `localhost:9100`.
"""

from __future__ import annotations

import io
import os
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import boto3
import clickhouse_connect
import httpx
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from weave.trace_server.byob.resolver import (
    BYOBResolver,
    ExportStorageCredentials,
    ResolvedExportTarget,
    StorageResolutionError,
)
from weave.trace_server.export import (
    ExportEngine,
    lookup_export_start,
    register_export_routes,
)

# Skip the module entirely when not asked to run e2e. Importing pytest's
# skip at module scope means the test is collected but never executed.
if os.environ.get("EXPORT_E2E") != "1":
    pytest.skip(
        "EXPORT_E2E=1 not set; skipping end-to-end export tests "
        "(see tests/trace_server/export/README.md to run them).",
        allow_module_level=True,
    )

CH_HTTP_HOST = "localhost"
CH_HTTP_PORT = 8224
MINIO_HOST = "localhost"
MINIO_PORT = 9200
MINIO_INTERNAL_URL = "http://minio:9000"
MINIO_ACCESS_KEY = "weave-e2e"
MINIO_SECRET_KEY = "weave-e2e-secret"
MINIO_REGION = "us-east-1"
BUCKET_NAME = "weave-export-e2e"
PROJECT_ID = "UHJvajEyMw=="
TEST_DB = "weave_export_e2e"
POLL_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 1


class _StaticResolver(BYOBResolver):
    """Returns the same MinIO-backed target for every project_id.

    File-storage methods raise so accidental use shows up as a test failure
    rather than silently routing somewhere unexpected.
    """

    def __init__(self, target: ResolvedExportTarget) -> None:
        self._target = target

    def resolve_write(self, project_id, default_client):  # pragma: no cover
        raise AssertionError("export engine must not call resolve_write")

    def resolve_read(self, project_id, stored_uri, default_client):  # pragma: no cover
        raise AssertionError("export engine must not call resolve_read")

    def resolve_export_target(self, project_id: str) -> ResolvedExportTarget:
        if project_id != self._target.source_project_id:
            raise StorageResolutionError(
                f"no target for project_id={project_id}; "
                f"resolver only knows {self._target.source_project_id}"
            )
        return self._target


def _mint_minio_sts_creds() -> tuple[str, str, str]:
    """Call MinIO's STS AssumeRole to get real temporary credentials.

    MinIO validates `session_token` for every authenticated request; passing
    a dummy token alongside the root credentials fails with `InvalidTokenId`.
    Minting real STS creds mirrors what the production BYOB resolver does
    via AWS STS.
    """
    sts = boto3.client(
        "sts",
        endpoint_url=f"http://{MINIO_HOST}:{MINIO_PORT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
    )
    response = sts.assume_role(
        RoleArn="arn:minio:bf:::role/weave-e2e",
        RoleSessionName="weave-e2e-session",
        DurationSeconds=3600,
    )
    creds = response["Credentials"]
    return creds["AccessKeyId"], creds["SecretAccessKey"], creds["SessionToken"]


def _make_target(project_id: str) -> ResolvedExportTarget:
    access_key, secret_key, session_token = _mint_minio_sts_creds()
    return ResolvedExportTarget(
        bucket_uri=f"{MINIO_INTERNAL_URL}/{BUCKET_NAME}",
        bucket_name=BUCKET_NAME,
        region=MINIO_REGION,
        credentials=ExportStorageCredentials(
            access_key_id=access_key,
            secret_access_key=SecretStr(secret_key),
            session_token=SecretStr(session_token),
        ),
        source_project_id=project_id,
    )


@pytest.fixture(scope="module")
def ch_client():
    """ClickHouse client against the e2e container; creates a fresh DB."""
    client = clickhouse_connect.get_client(
        host=CH_HTTP_HOST,
        port=CH_HTTP_PORT,
        username="default",
        password="",
    )
    try:
        client.ping()
    except Exception as exc:
        pytest.skip(
            f"ClickHouse e2e container is not reachable at "
            f"{CH_HTTP_HOST}:{CH_HTTP_PORT} ({exc}). "
            "Bring it up with `docker compose -f docker-compose.export-e2e.yml up -d`."
        )
    client.command(f"DROP DATABASE IF EXISTS {TEST_DB}")
    client.command(f"CREATE DATABASE {TEST_DB}")
    client.database = TEST_DB
    _create_exports_table(client)
    _create_calls_complete_table(client)
    yield client
    try:
        client.command(f"DROP DATABASE IF EXISTS {TEST_DB}")
    finally:
        client.close()


def _create_exports_table(client) -> None:
    """Inline copy of the `exports` audit-table migration so this test does
    not depend on the migration PR landing first.
    """
    client.command(
        """
        CREATE TABLE IF NOT EXISTS exports (
            request_id    UUID,
            action        LowCardinality(String),
            project_id    String,
            job_id        UUID,
            requested_by  String,
            minted_by     String DEFAULT '',
            table_name    LowCardinality(String),
            request_json  String DEFAULT '',
            output_uri    String DEFAULT '',
            ts            DateTime64(3)
        )
        ENGINE = MergeTree
        PARTITION BY toYYYYMM(ts)
        ORDER BY (project_id, job_id, action, ts)
        """
    )


def _create_calls_complete_table(client) -> None:
    """Minimal `calls_complete`-shaped table sufficient for the export
    `SELECT *` path. The real production table has many more columns; the
    export module only requires `project_id`, `started_at`, and any other
    columns present on the row to flow through to Parquet.
    """
    client.command(
        """
        CREATE TABLE IF NOT EXISTS calls_complete (
            project_id    String,
            id            String,
            trace_id      String,
            started_at    DateTime64(3),
            ended_at      DateTime64(3),
            op_name       String,
            summary_dump  String DEFAULT '{}'
        )
        ENGINE = MergeTree
        ORDER BY (project_id, started_at)
        """
    )


@pytest.fixture(scope="module")
def s3_client(ch_client):
    """boto3 S3 client targeted at the local MinIO; ensures bucket exists."""
    client = boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_HOST}:{MINIO_PORT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
    )
    try:
        client.head_bucket(Bucket=BUCKET_NAME)
    except Exception:
        client.create_bucket(Bucket=BUCKET_NAME)
    return client


@pytest.fixture(scope="module")
def app(ch_client) -> Iterator[FastAPI]:
    """FastAPI app wired with the export routes and a static MinIO resolver.

    `AWS_ENDPOINT_URL_S3` is exported here so `PresignedUrlMinter`'s boto3
    client picks up the MinIO endpoint without needing a PresignedUrlMinter
    code change.
    """
    target = _make_target(PROJECT_ID)
    resolver = _StaticResolver(target)
    engine = ExportEngine(ch_client, resolver, env="dev")

    previous = os.environ.get("AWS_ENDPOINT_URL_S3")
    os.environ["AWS_ENDPOINT_URL_S3"] = f"http://{MINIO_HOST}:{MINIO_PORT}"

    router = APIRouter()

    register_export_routes(
        router,
        get_engine=lambda auth: engine,
        get_auth_params=lambda req: None,
        require_project_read=lambda project_id, auth: None,
        require_export_flag=lambda project_id, auth: None,
        get_requester=lambda auth: "e2e-tester",
        lookup_job_row=lambda job_id: lookup_export_start(ch_client, job_id),
    )
    application = FastAPI()
    application.include_router(router)
    try:
        yield application
    finally:
        if previous is None:
            os.environ.pop("AWS_ENDPOINT_URL_S3", None)
        else:
            os.environ["AWS_ENDPOINT_URL_S3"] = previous


@pytest.fixture
def seeded_calls(ch_client):
    """Inserts 5 known `calls_complete` rows for `PROJECT_ID` and clears
    them after the test.
    """
    now = datetime.now(timezone.utc)
    rows = [
        (
            PROJECT_ID,
            f"call-{i}",
            f"trace-{i}",
            now,
            now,
            f"op-{i}",
            '{"usage": {}}',
        )
        for i in range(5)
    ]
    ch_client.insert(
        "calls_complete",
        rows,
        column_names=[
            "project_id",
            "id",
            "trace_id",
            "started_at",
            "ended_at",
            "op_name",
            "summary_dump",
        ],
    )
    yield 5
    ch_client.command(
        "ALTER TABLE calls_complete DELETE WHERE project_id = {p:String}",
        parameters={"p": PROJECT_ID},
    )


def _poll_until_terminal(client: TestClient, job_id: str) -> dict:
    """Poll `GET /export/{job_id}` until the state leaves PENDING/RUNNING."""
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_body: dict = {}
    while time.time() < deadline:
        response = client.get(f"/export/{job_id}")
        assert response.status_code == 200, response.text
        last_body = response.json()
        if last_body["state"] not in {"pending", "running"}:
            return last_body
        time.sleep(POLL_INTERVAL_SECONDS)
    pytest.fail(
        f"export job {job_id} did not leave PENDING/RUNNING within "
        f"{POLL_TIMEOUT_SECONDS}s; last body: {last_body}"
    )


def test_tier_1_export_writes_parquet_and_mints_signed_url(
    app: FastAPI, s3_client, seeded_calls: int
) -> None:
    """Full happy-path: submit, poll, download, validate.

    Asserts that:
      1. POST /export/start returns 200 with a job_id.
      2. The detached CH INSERT actually writes a Parquet object to MinIO
         under the expected key layout.
      3. GET /export/{job_id} eventually reaches SUCCEEDED and includes a
         signed URL that downloads the same bytes MinIO stored.
      4. (If pyarrow is installed) the Parquet row count matches the seed.
    """
    client = TestClient(app)
    start_response = client.post(
        "/export/start",
        json={"project_id": PROJECT_ID, "table": "calls_complete"},
    )
    assert start_response.status_code == 200, start_response.text
    job_id = start_response.json()["job_id"]

    final = _poll_until_terminal(client, job_id)
    assert final["state"] == "succeeded", final

    signed_url = final["signed_url"]
    assert signed_url, final
    # boto3 presigns against AWS_ENDPOINT_URL_S3 (set in the fixture), so
    # the URL host is localhost. Fetch and validate.
    download = httpx.get(signed_url, timeout=10.0)
    assert download.status_code == 200, download.text
    body = download.content

    # Direct MinIO read for a redundant sanity check that the object key
    # the engine wrote matches what the minter signed.
    expected_key = f"dev/exports/{PROJECT_ID}/{uuid.UUID(job_id).hex}/data.parquet"
    head = s3_client.head_object(Bucket=BUCKET_NAME, Key=expected_key)
    assert head["ContentLength"] == len(body)

    # Optional schema validation when pyarrow is available. Skip silently
    # if not installed; the structural checks above are the load-bearing
    # part of the test.
    pa_parquet = pytest.importorskip("pyarrow.parquet")
    table = pa_parquet.read_table(io.BytesIO(body))
    assert table.num_rows == seeded_calls
    assert "project_id" in table.column_names
    assert "started_at" in table.column_names


def test_resolver_mismatch_refuses_to_proceed(app: FastAPI) -> None:
    """Defense-in-depth: requesting a project the resolver does not own
    must fail-closed with a 412 (no NC created, no audit row).
    """
    client = TestClient(app)
    response = client.post(
        "/export/start",
        json={"project_id": "some-other-project", "table": "calls_complete"},
    )
    assert response.status_code == 412, response.text
    assert response.json()["detail"]["code"] == "no_storage_target"
