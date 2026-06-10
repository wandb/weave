"""One-off bulk export to a W&B-owned bucket + presigned download URL(s).

Interim path while team-level BYOB is in security/design review. ClickHouse
writes the project's Parquet directly to a bucket WE own (real platform
creds, native multipart, any size), then we mint short-TTL presigned GETs for
the customer. No gorilla, no BYOB resolver, no presigned-write (which CH
can't do anyway). This is the bulk-export spec minus the BYOB target.

Security posture baked in (see weave/trace_server/export, spec
`weave-bulk-export.md`):
  - dedicated export bucket, never the shared trace-file bucket
  - short URL TTL (default 15m); each URL is a bearer token to one file
  - signer identity must have no s3:ListBucket (can't enumerate sibling keys)
  - one audit row per start/mint/terminal; refuses to run without the table
  - do NOT run this for a customer who asked for BYOB on residency grounds:
    it lands their data in our tenancy, the opposite of what they want.

Credentials come from the environment (EXPORT_AKID / EXPORT_SECRET /
EXPORT_SESSION_TOKEN / CH_PASSWORD), never argv, so they don't leak via `ps`
or shell history.

Chunking: estimates compressed size from a byte-size preflight and splits
into ~256MB Parquet files via `PARTITION BY cityHash64(id) % n`. Sizing is by
bytes, not rows (measured 58-6,324 bytes/row across row shapes). The exact
set of non-empty partitions is read back from CH so the manifest reflects
what was actually written rather than a guess.
"""

import argparse
import datetime
import json
import math
import os
import re
import sys
import uuid
from dataclasses import dataclass

import boto3
import clickhouse_connect
from botocore.client import Config
from clickhouse_connect.driver.client import Client


@dataclass(frozen=True)
class TableSpec:
    time_column: str
    id_column: str
    final: bool  # AggregatingMergeTree (calls_merged) MUST merge or rows are fragments


TABLES = {
    "calls_complete": TableSpec("started_at", "id", final=False),
    "spans": TableSpec("started_at", "span_id", final=False),
    "calls_merged": TableSpec("started_at", "id", final=True),
}

DEFAULT_TTL_MINUTES = 15
MAX_EXPORT_QUERY_SECONDS = 1800
TARGET_FILE_BYTES = 256 * 1024 * 1024
# Conservative vs the measured 4.2-5.2x so the estimate slightly OVER-counts
# size -> more, smaller files. Safe direction for download UX.
ZSTD_RATIO = 4.0

# Exactly entity/project, each segment from a safe charset; `..` rejected
# separately since it would escape the key prefix.
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TIMESTAMP_RE = re.compile(r"^[0-9 :.T+-]+$")
# STS-issued AWS creds live in this charset; reject anything that could break
# out of the single-quoted s3() literal.
CREDENTIAL_RE = re.compile(r"^[A-Za-z0-9/+=._-]+$")
# Operator-supplied bucket / endpoint / env also land in the s3() URL literal.
DEST_VALUE_RE = re.compile(r"^[A-Za-z0-9._:/-]+$")


def plan_export(
    ch: Client, *, table: str, where: str, target_bytes: int = TARGET_FILE_BYTES
) -> tuple[int, int, float]:
    """Return (rows, n_files, est_compressed_bytes). One scan: count + avg row bytes."""
    spec = TABLES[table]
    row = ch.query(
        f"SELECT count(), sum(byteSize(*)) FROM {table}{_final(spec)} WHERE {where}"
    ).result_rows[0]
    rows, uncompressed = int(row[0]), int(row[1] or 0)
    est_compressed = uncompressed / ZSTD_RATIO
    n_files = max(1, math.ceil(est_compressed / target_bytes)) if rows else 0
    return rows, n_files, est_compressed


def partition_row_counts(
    ch: Client, *, table: str, where: str, n_files: int
) -> dict[int, int]:
    """Read back the exact non-empty `cityHash64(id) % n` partitions + row counts,
    so the manifest reflects what was written rather than an assumption.
    """
    spec = TABLES[table]
    rows = ch.query(
        f"SELECT cityHash64({spec.id_column}) % {n_files} AS p, count() "
        f"FROM {table}{_final(spec)} WHERE {where} GROUP BY p ORDER BY p"
    ).result_rows
    return {int(p): int(c) for p, c in rows}


def export_project(
    ch: Client,
    *,
    table: str,
    where: str,
    dest_base: str,
    n_files: int,
    parts: dict[int, int],
    akid: str,
    secret: str,
    session_token: str | None,
    job_id: uuid.UUID,
) -> list[str]:
    """Write the project's Parquet (single `data.parquet` or `PARTITION BY` parts) and return key suffixes."""
    for value in (akid, secret, session_token):
        if value is not None and not CREDENTIAL_RE.match(value):
            sys.exit("credential contains characters outside the allowed charset")
    cred_args = f"'{akid}', '{secret}'" + (
        f", '{session_token}'" if session_token else ""
    )
    spec = TABLES[table]
    settings = (
        f"s3_truncate_on_insert = 1, max_execution_time = {MAX_EXPORT_QUERY_SECONDS}, "
        f"output_format_parquet_compression_method = 'zstd'"
    )
    if n_files == 1:
        ch.command(
            f"INSERT INTO FUNCTION s3('{dest_base}/data.parquet', {cred_args}, format = 'Parquet') "
            f"SELECT * FROM {table}{_final(spec)} WHERE {where} SETTINGS {settings}",
            settings={"query_id": str(job_id)},
        )
        return ["data.parquet"]

    ch.command(
        # `{_partition_id}` is CH's filename token (sent literally, not a query param);
        # max_partitions_per_insert_block defaults to 100, so raise it to cover n_files.
        f"INSERT INTO FUNCTION s3('{dest_base}/data_{{_partition_id}}.parquet', {cred_args}, "
        f"format = 'Parquet') PARTITION BY (cityHash64({spec.id_column}) % {n_files}) "
        f"SELECT * FROM {table}{_final(spec)} WHERE {where} "
        f"SETTINGS {settings}, max_partitions_per_insert_block = {n_files}",
        settings={"query_id": str(job_id)},
    )
    return [f"data_{p}.parquet" for p in sorted(parts)]


def mint_download_urls(
    s3, *, bucket: str, prefix: str, suffixes: list[str], ttl_minutes: int
) -> tuple[list[dict], datetime.datetime]:
    """Mint a presigned GET per expected part; every HEAD must succeed.

    A failure (incl. the no-ListBucket 403 on a missing key) is real, never skipped.
    """
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=ttl_minutes
    )
    parts: list[dict] = []
    for suffix in suffixes:
        key = f"{prefix}/{suffix}"
        size = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl_minutes * 60,
            HttpMethod="GET",
        )
        parts.append({"key": key, "bytes": size, "url": url})
    return parts, expires_at


def write_audit(
    ch: Client,
    *,
    action: str,
    project_id: str,
    job_id: uuid.UUID,
    requested_by: str,
    table: str,
    output_uri: str,
    request_json: str = "",
    minted_by: str = "",
    allow_missing: bool = False,
) -> None:
    """Append one `exports` audit row; refuse to run if the table is missing (override via --allow-no-audit)."""
    if not ch.query(
        "SELECT count() FROM system.tables WHERE database = currentDatabase() AND name = 'exports'"
    ).result_rows[0][0]:
        if allow_missing:
            print(
                "WARN: --allow-no-audit set; proceeding without an audit trail",
                file=sys.stderr,
            )
            return
        sys.exit(
            "no `exports` audit table in this database; refusing to export "
            "without an audit trail (pass --allow-no-audit to override)"
        )
    ch.insert(
        "exports",
        [
            [
                uuid.uuid4(),
                action,
                project_id,
                job_id,
                requested_by,
                minted_by,
                table,
                request_json,
                output_uri,
                datetime.datetime.now(datetime.timezone.utc),
            ]
        ],
        column_names=[
            "request_id",
            "action",
            "project_id",
            "job_id",
            "requested_by",
            "minted_by",
            "table_name",
            "request_json",
            "output_uri",
            "ts",
        ],
    )


def build_where(
    table: str, project_id: str, time_start: str | None, time_end: str | None
) -> str:
    """Validated, inlined WHERE (no param binding: it would collide with CH's
    `{_partition_id}` filename token).
    """
    if not PROJECT_ID_RE.match(project_id) or ".." in project_id:
        sys.exit(f"invalid project_id (want entity/project): {project_id!r}")
    preds = [f"project_id = '{project_id}'"]
    for bound, op in ((time_start, ">="), (time_end, "<")):
        if bound:
            if not TIMESTAMP_RE.match(bound):
                sys.exit(f"invalid timestamp: {bound!r}")
            preds.append(f"{TABLES[table].time_column} {op} '{bound}'")
    return " AND ".join(preds)


def make_s3(
    endpoint: str | None, region: str, akid: str, secret: str, token: str | None
):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=akid,
        aws_secret_access_key=secret,
        aws_session_token=token,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _final(spec: TableSpec) -> str:
    return " FINAL" if spec.final else ""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-id", required=True, help="entity/project")
    p.add_argument("--table", default="calls_complete", choices=sorted(TABLES))
    p.add_argument("--time-start")
    p.add_argument("--time-end")
    p.add_argument("--env", default="prod")
    p.add_argument("--ttl-minutes", type=int, default=DEFAULT_TTL_MINUTES)
    p.add_argument(
        "--target-file-mb", type=int, default=TARGET_FILE_BYTES // 1024 // 1024
    )
    p.add_argument("--requested-by", default="oneoff-operator")
    p.add_argument("--allow-no-audit", action="store_true")
    p.add_argument("--ch-host", default="localhost")
    p.add_argument("--ch-port", type=int, default=8123)
    p.add_argument("--ch-database", default="default")
    p.add_argument("--bucket", required=True)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--dest-endpoint", required=True, help="endpoint CH writes to")
    p.add_argument(
        "--presign-endpoint", help="download endpoint (defaults to --dest-endpoint)"
    )
    args = p.parse_args()

    akid, secret = os.environ.get("EXPORT_AKID"), os.environ.get("EXPORT_SECRET")
    if not akid or not secret:
        sys.exit("set EXPORT_AKID and EXPORT_SECRET in the environment")
    session_token = os.environ.get("EXPORT_SESSION_TOKEN")

    ch = clickhouse_connect.get_client(
        host=args.ch_host,
        port=args.ch_port,
        database=args.ch_database,
        password=os.environ.get("CH_PASSWORD", ""),
        send_receive_timeout=MAX_EXPORT_QUERY_SECONDS,
    )
    for label, value in (
        ("bucket", args.bucket),
        ("dest-endpoint", args.dest_endpoint),
        ("presign-endpoint", args.presign_endpoint),
        ("env", args.env),
    ):
        if value and not DEST_VALUE_RE.match(value):
            sys.exit(f"--{label} contains characters outside the allowed charset")

    job_id = uuid.uuid4()
    where = build_where(args.table, args.project_id, args.time_start, args.time_end)
    prefix = f"{args.env}/exports/{args.project_id}/{job_id.hex}"
    slice_json = json.dumps(
        {
            "table": args.table,
            "time_start": args.time_start,
            "time_end": args.time_end,
            "where": where,
        }
    )

    rows, n_files, est = plan_export(
        ch,
        table=args.table,
        where=where,
        target_bytes=args.target_file_mb * 1024 * 1024,
    )
    print(
        f"preflight: {rows:,} rows, est {est / 1024 / 1024:.0f} MB compressed -> {n_files} file(s)"
    )
    if rows == 0:
        sys.exit("nothing to export (0 rows)")

    write_audit(
        ch,
        action="EXPORT_START",
        project_id=args.project_id,
        job_id=job_id,
        requested_by=args.requested_by,
        table=args.table,
        output_uri=prefix,
        request_json=slice_json,
        allow_missing=args.allow_no_audit,
    )
    try:
        parts_counts = (
            partition_row_counts(ch, table=args.table, where=where, n_files=n_files)
            if n_files > 1
            else {0: rows}
        )
        if sum(parts_counts.values()) != rows:
            sys.exit(
                f"partition counts {sum(parts_counts.values())} != preflight {rows}"
            )

        suffixes = export_project(
            ch,
            table=args.table,
            where=where,
            dest_base=f"{args.dest_endpoint.rstrip('/')}/{args.bucket}/{prefix}",
            n_files=n_files,
            parts=parts_counts,
            akid=akid,
            secret=secret,
            session_token=session_token,
            job_id=job_id,
        )
        s3 = make_s3(
            args.presign_endpoint or args.dest_endpoint,
            args.region,
            akid,
            secret,
            session_token,
        )
        urls, expires_at = mint_download_urls(
            s3,
            bucket=args.bucket,
            prefix=prefix,
            suffixes=suffixes,
            ttl_minutes=args.ttl_minutes,
        )
    except BaseException:
        write_audit(
            ch,
            action="EXPORT_FAILED",
            project_id=args.project_id,
            job_id=job_id,
            requested_by=args.requested_by,
            table=args.table,
            output_uri=prefix,
            allow_missing=True,
        )
        raise

    write_audit(
        ch,
        action="EXPORT_MINT",
        project_id=args.project_id,
        job_id=job_id,
        requested_by=args.requested_by,
        table=args.table,
        output_uri=prefix,
        minted_by=args.requested_by,
        allow_missing=args.allow_no_audit,
    )
    write_audit(
        ch,
        action="EXPORT_COMPLETE",
        project_id=args.project_id,
        job_id=job_id,
        requested_by=args.requested_by,
        table=args.table,
        output_uri=prefix,
        allow_missing=args.allow_no_audit,
    )

    manifest = {
        "job_id": job_id.hex,
        "project_id": args.project_id,
        "table": args.table,
        "rows": rows,
        "n_files": len(urls),
        "expires_at": expires_at.isoformat(),
        "parts": [
            {"key": u["key"], "bytes": u["bytes"], "url": u["url"]} for u in urls
        ],
    }
    print(json.dumps(manifest, indent=2))
    total_mb = sum(u["bytes"] for u in urls) / 1024 / 1024
    # NOTE: with STS session creds, the URLs also die when the SESSION expires,
    # regardless of ttl-minutes; fine at 15m, watch it for short-lived creds.
    print(
        f"\n{len(urls)} file(s), {total_mb:.1f} MB total, URLs expire {expires_at.isoformat()}"
    )


if __name__ == "__main__":
    main()
