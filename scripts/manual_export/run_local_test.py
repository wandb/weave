"""Local end-to-end test of the one-off export against MinIO (= our bucket).

Exercises the single-file, chunked (PARTITION BY), and >100-partition paths,
plus the security properties: no cross-project leak, presigned URL bound to
one key + expiry, audit trail (start/mint/complete) written.

Assumes a CH + MinIO stack on the `bexp` docker network:
  CH at localhost:8133 (password 'stress'); reaches MinIO at bexp-minio:9000
  MinIO S3 API at localhost:9400 (root / rootroot123), bucket 'exports'
"""

import io
import json
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

import clickhouse_connect
import manual_export as ox
import pyarrow.parquet as pq

CH = {"host": "localhost", "port": 8133, "password": "stress"}
INTERNAL_ENDPOINT = "http://bexp-minio:9000"
HOST_ENDPOINT = "http://localhost:9400"
BUCKET = "exports"
PROJECT = "acme/prod"
OTHER_PROJECT = "other/proj"
ROOT_KEY, ROOT_SECRET = "root", "rootroot123"
SEED_ROWS = 40_000


def seed(client) -> None:
    client.command("DROP TABLE IF EXISTS calls_complete")
    client.command("DROP TABLE IF EXISTS exports")
    client.command(
        """
        CREATE TABLE calls_complete (
            id String, project_id String, created_at DateTime64(3) DEFAULT now64(3),
            trace_id String, op_name String, started_at DateTime64(6),
            inputs_dump String, output_dump String, summary_dump String, attributes_dump String
        ) ENGINE = ReplacingMergeTree(created_at)
        PARTITION BY toYYYYMM(started_at) ORDER BY (project_id, started_at, id)
        """
    )
    client.command(
        """
        CREATE TABLE IF NOT EXISTS exports (
            request_id UUID, action LowCardinality(String), project_id String, job_id UUID,
            requested_by String, minted_by String DEFAULT '', table_name LowCardinality(String),
            request_json String DEFAULT '', output_uri String DEFAULT '', ts DateTime64(3)
        ) ENGINE = MergeTree PARTITION BY toYYYYMM(ts) ORDER BY (project_id, job_id, action, ts)
        """
    )
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cols = [
        "id",
        "project_id",
        "trace_id",
        "op_name",
        "started_at",
        "inputs_dump",
        "output_dump",
        "summary_dump",
        "attributes_dump",
    ]

    def rows_for(project: str, n: int) -> list:
        return [
            [
                uuid.uuid4().hex,
                project,
                uuid.uuid4().hex,
                "op/chat",
                base + timedelta(seconds=i),
                json.dumps(
                    {"messages": [{"role": "user", "content": f"hello {i} " * 8}]}
                ),
                json.dumps({"choices": [{"message": {"content": f"hi {i} " * 8}}]}),
                json.dumps({"usage": {"total_tokens": i % 500}}),
                json.dumps({"env": "prod"}),
            ]
            for i in range(n)
        ]

    client.insert("calls_complete", rows_for(PROJECT, SEED_ROWS), column_names=cols)
    client.insert("calls_complete", rows_for(OTHER_PROJECT, 5_000), column_names=cols)


def run_case(
    client, s3, *, label: str, target_mb: int | None = None, force_n: int | None = None
) -> list[dict]:
    job_id = uuid.uuid4()
    where = ox.build_where("calls_complete", PROJECT, None, None)
    rows, n_files, est = ox.plan_export(
        client,
        table="calls_complete",
        where=where,
        target_bytes=(target_mb or 256) * 1024 * 1024,
    )
    if force_n is not None:
        n_files = force_n
    prefix = f"test/exports/{PROJECT}/{job_id.hex}"

    ox.write_audit(
        client,
        action="EXPORT_START",
        project_id=PROJECT,
        job_id=job_id,
        requested_by="tester",
        table="calls_complete",
        output_uri=prefix,
    )
    parts_counts = (
        ox.partition_row_counts(
            client, table="calls_complete", where=where, n_files=n_files
        )
        if n_files > 1
        else {0: rows}
    )
    assert sum(parts_counts.values()) == rows, "partition counts != preflight"

    suffixes = ox.export_project(
        client,
        table="calls_complete",
        where=where,
        dest_base=f"{INTERNAL_ENDPOINT}/{BUCKET}/{prefix}",
        n_files=n_files,
        parts=parts_counts,
        akid=ROOT_KEY,
        secret=ROOT_SECRET,
        session_token=None,
        job_id=job_id,
    )
    parts, _ = ox.mint_download_urls(
        s3, bucket=BUCKET, prefix=prefix, suffixes=suffixes, ttl_minutes=15
    )
    ox.write_audit(
        client,
        action="EXPORT_MINT",
        project_id=PROJECT,
        job_id=job_id,
        requested_by="tester",
        table="calls_complete",
        output_uri=prefix,
        minted_by="tester",
    )
    ox.write_audit(
        client,
        action="EXPORT_COMPLETE",
        project_id=PROJECT,
        job_id=job_id,
        requested_by="tester",
        table="calls_complete",
        output_uri=prefix,
    )

    total_rows, projects, sizes = 0, set(), []
    for part in parts:
        with urllib.request.urlopen(part["url"]) as resp:
            body = resp.read()
        tbl = pq.read_table(io.BytesIO(body))
        total_rows += tbl.num_rows
        projects |= set(tbl.column("project_id").to_pylist())
        sizes.append(part["bytes"])

    print(
        f"[{label}] {n_files} planned, {len(parts)} written; rows {total_rows:,}; "
        f"max part {max(sizes) / 1024 / 1024:.2f}MB; projects {projects}"
    )
    assert total_rows == SEED_ROWS, f"row total {total_rows} != {SEED_ROWS}"
    assert projects == {PROJECT}, f"LEAK: {projects}"
    assert len(parts) == len(suffixes), "missing part(s) in manifest"
    return parts


def assert_url_scoped(parts: list[dict]) -> None:
    """A presigned GET is bound to one key + expiry: tampering either -> 403."""

    def code(u: str) -> int:
        try:
            urllib.request.urlopen(u)
        except urllib.error.HTTPError as e:
            return e.code
        else:
            return 200

    url = parts[0]["url"]
    assert code(url) == 200, "valid URL should download"
    assert code(url.replace("acme/prod", "victim/prod")) == 403, (
        "tampered key should 403"
    )
    assert code(url.replace("X-Amz-Expires=900", "X-Amz-Expires=99999")) == 403, (
        "tampered TTL should 403"
    )


def main() -> None:
    client = clickhouse_connect.get_client(**CH, send_receive_timeout=120)
    client.command("CREATE DATABASE IF NOT EXISTS oneoff")
    client.database = "oneoff"
    seed(client)
    s3 = ox.make_s3(HOST_ENDPOINT, "us-east-1", ROOT_KEY, ROOT_SECRET, None)

    print("=== one-off export local test ===")
    single = run_case(client, s3, label="single", target_mb=256)
    run_case(client, s3, label="chunked", target_mb=1)
    run_case(client, s3, label=">100 parts", force_n=120)
    assert_url_scoped(single)

    audit = client.query(
        "SELECT action, count() FROM exports WHERE project_id={p:String} GROUP BY action ORDER BY action",
        parameters={"p": PROJECT},
    ).result_rows
    print(f"audit rows: {audit}")
    assert dict(audit) == {"EXPORT_START": 3, "EXPORT_MINT": 3, "EXPORT_COMPLETE": 3}, (
        "audit mismatch"
    )
    print(
        "\nPASS: single + chunked + >100-part export all rows, no leak, "
        "URL key/TTL-scoped, full audit trail"
    )


if __name__ == "__main__":
    main()
