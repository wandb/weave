# Manual bulk export (interim, operator-run)

A one-off, operator-run bulk export of a Weave project's data to a **W&B-owned**
bucket, handed to the customer as short-TTL presigned download URLs. This is the
bridge while team-level BYOB is in security/design review.

It is deliberately the [bulk-export spec](../../../../specs/weave-bulk-export.md)
**minus the BYOB target**: ClickHouse writes Parquet directly to a bucket we own
(real platform creds, native multipart), then we presign GETs. Because we hold
the bucket creds, there is no presigned-*write* problem (ClickHouse cannot write
to a presigned URL; it SigV4-signs its own writes).

## When to use / NOT use

- **Use** for customers whose ask is "get my data out."
- **Do NOT use** for a customer who requested BYOB on **data-residency** grounds.
  This lands their data in our tenancy, the opposite of what they need, and may
  breach a residency/DPA commitment. Those customers wait for BYOB.

## Procedure

1. **Preflight + plan** — `count()` + `sum(byteSize(*))` in one scan; estimate
   compressed size (`/ 4.0` zstd) and split into ~256 MB files.
2. **Audit** — write an `EXPORT_START` row to `exports`.
3. **Write** — `INSERT INTO FUNCTION s3(<our-bucket>, <creds>, Parquet) SELECT *
   FROM <table> WHERE project_id=…`. One file, or many via
   `PARTITION BY cityHash64(id) % n` into `data_{_partition_id}.parquet`.
4. **Mint** — presigned GET per part (15 min TTL); write `EXPORT_MINT`.
5. **Deliver** — emit a manifest of `{key, bytes, url}` parts.

## File-size / chunking rationale (measured)

- Target **~256 MB compressed** per Parquet file (industry-consensus sweet spot).
- Size by **bytes, not rows**: measured **58-6,324 bytes/row** across row shapes
  (skinny calls vs fat multimodal), a 109x spread, so a fixed rows-per-file is
  wrong. `n = ceil(rows * avg_row_bytes / zstd_ratio / 256MB)`.
- `cityHash64(id) % n` distributes uniformly (measured CV 0.5%).
- Encode time is **not** the constraint (~100M rows in minutes, under the 1800s
  query budget); we chunk for download UX and consumer-tool compatibility.

## Security posture (baked into the script)

- **Dedicated export bucket**, never the shared trace-file bucket; SSE-KMS, not
  public, no anonymous access.
- **Short object lifetime** (hours, via bucket lifecycle) — we hold a full copy
  only transiently.
- **Each presigned URL is a bearer token to one file.** TTL 15 min, HTTPS,
  full-object-key-scoped (tampering the key or expiry invalidates the signature),
  and the signer identity must have **no `s3:ListBucket`** (can't enumerate
  sibling keys).
- **One audit row per start and per mint** — the record of "we materialized
  customer X's data at T and user Y downloaded it."
- Creds are passed as `s3()` args; in prod the cluster's `query_masking_rules`
  redact them from every log surface (same as BYOB).

## Run it (prod)

Credentials come from the environment (never argv, so they don't leak via
`ps`/shell history). The identity must be scoped to the export prefix with
**no `s3:ListBucket`**.

```bash
export EXPORT_AKID=... EXPORT_SECRET=...   # EXPORT_SESSION_TOKEN if STS; CH_PASSWORD if set
python manual_export.py \
  --project-id ENTITY/PROJECT --table calls_complete \
  --dest-endpoint https://s3.us-east-1.amazonaws.com \
  --bucket wandb-weave-exports --region us-east-1 --env prod
```

`--time-start/--time-end` narrow the range; `--target-file-mb` overrides the
256 MB default. `calls_merged` is read with **FINAL** so customers get merged
rows, not raw start/end fragments (affordable for a one-off; the no-FINAL
optimization is only for the automated hot-path export).

## Verify locally

`run_local_test.py` runs the full flow (single + chunked + >100 partitions)
against MinIO and asserts: all rows exported, no cross-project leak, presigned
URL bound to one key + expiry, full start/mint/complete audit trail.

```bash
docker network create bexp
docker run -d --name bexp-minio --network bexp -p 9400:9000 \
  -e MINIO_ROOT_USER=root -e MINIO_ROOT_PASSWORD=rootroot123 minio/minio server /data
docker run -d --name bexp-ch --network bexp -p 8133:8123 -m 6g \
  -e CLICKHOUSE_PASSWORD=stress clickhouse/clickhouse-server:26.3
docker run --rm --network bexp --entrypoint sh minio/mc -c \
  "until mc alias set m http://bexp-minio:9000 root rootroot123; do sleep 1; done; mc mb -p m/exports"

uv run --group test python scripts/manual_export/run_local_test.py
# teardown: docker rm -f bexp-ch bexp-minio && docker network rm bexp
```
