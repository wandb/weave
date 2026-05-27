# Export module tests

Two layers of tests live here:

| File | What it covers | Needs Docker? |
|---|---|---|
| `test_engine.py`, `test_sql_builders.py`, `test_escaping.py`, `test_state.py`, `test_table_registry.py`, `test_sweeper.py`, `test_costs_sql.py` | Orchestration logic against a fake CH client (`_FakeClient`) | No |
| `test_export_integration.py` | End-to-end through a real ClickHouse + MinIO stack | Yes |

## Running the end-to-end test locally

The integration test is skipped unless `EXPORT_E2E=1` is set. It expects a
ClickHouse + MinIO docker-compose stack to be running. Ports are offset
from the `.tilt/*` dev compose files so you can run this alongside Tilt
without conflicts.

```bash
# 1. Bring up the e2e stack (CH on localhost:8224, MinIO on localhost:9200)
docker compose -f services/weave-python/weave-public/tests/trace_server/export/docker-compose.export-e2e.yml up -d

# 2. Install pyarrow (required for Parquet schema validation)
cd services/weave-python/weave-public
uv pip install pyarrow

# 3. Run the test
EXPORT_E2E=1 uv run --group test python -m pytest \
    tests/trace_server/export/test_export_integration.py -v

# 4. Tear down when done
docker compose -f services/weave-python/weave-public/tests/trace_server/export/docker-compose.export-e2e.yml down -v
```

### What it actually exercises

- `POST /export/start` submits a detached `INSERT INTO FUNCTION s3(...)` against
  MinIO via a temporary `CREATE NAMED COLLECTION` carrying STS credentials.
- The fixture mints **real** temporary credentials via MinIO's STS
  `AssumeRole` (MinIO rejects requests with a `session_token` that doesn't
  match a live STS session, so a dummy token won't fly).
- `GET /export/{job_id}` polls `system.query_log` until the query terminates,
  then mints a presigned URL via `PresignedUrlMinter` targeted at the local
  MinIO (the fixture exports `AWS_ENDPOINT_URL_S3` so boto3 picks it up).
- The test downloads the presigned URL, cross-checks the bytes against a
  direct MinIO `head_object`, and (via `pyarrow.parquet`) validates the
  Parquet row count and column shape.
- A second test confirms the `source_project_id` defense-in-depth check
  rejects a request whose project_id does not match the resolver's target.

### Important config caveats

- **CH version pinned to 25.12**, not the 26.2 that the rest of the repo
  runs against. CH 26.2 changed `named_collection_control` behavior in a
  way that blocks the engine's `CREATE NAMED COLLECTION` even with
  `access_management=1`. Once the upstream change is reproducible in
  production the pin can move; until then, 25.12 is the version this test
  has been validated against.
- The `zz-access.xml` config filename is deliberate. The CH entrypoint
  generates `default-user.xml` with `<default remove="remove">` which
  wipes the existing default user, then recreates it without
  `named_collection_control`. XML user-config files are merged in
  alphabetical order, so the override needs a name that sorts AFTER
  `default-user.xml` for its settings to survive.

### Why this doesn't depend on the migration PR

The `exports` audit table is created inline by the test fixture (matching
the migration in `weave/trace_server/migrations/`). This keeps the
integration test independent of merge order between the module branch and
the migration branch.
