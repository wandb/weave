# Message search backfill

Prerequisite: [message search storage and migration](message-search.md).

## Backfill

Apply the migration before choosing a cutoff. It installs capture without
copying historical data. New inserts build their text index immediately;
there is no separate `MATERIALIZE INDEX` pass for this migration.

Use the trace server's `WF_CLICKHOUSE_HOST`, `WF_CLICKHOUSE_PORT`,
`WF_CLICKHOUSE_USER`, `WF_CLICKHOUSE_PASS`, and `WF_CLICKHOUSE_DATABASE`
environment variables. Port 8443 uses TLS. Keep credentials out of command
arguments and checkpoint files.

```sh
uv run --group test python -m weave.trace_server.message_search_backfill \
  --checkpoint /durable/checkpoints/message-search.json \
  --window-hours 1 --max-threads 2 --max-memory-usage 4294967296
```

The first run records a server-time `created_at` cutoff, the source's complete
event-time bounds before that cutoff, and table UUIDs. `--before` can supply an
earlier UTC cutoff. It never derives coverage from the earliest target row.
`--project-id` limits a rehearsal or rollout to one project.

Each window copies both destinations and verifies content bytes, logical
occurrence keys, and latest metadata before atomically advancing the checkpoint.
A newer live occurrence may supersede historical metadata. Equal-version
conflicting metadata is ambiguous in ReplacingMergeTree and must be reconciled
before cutover. Retries reinsert the whole unfinished window; replacement makes
them logically idempotent even before background merges finish. Keep one worker
per checkpoint. The CLI takes an exclusive local file lock.

Run the same command to resume. Run with `--validate-only` to check all recorded
windows again, including previously completed ones. A failed validation leaves
the checkpoint unchanged. A fresh checkpoint replays data to repair missing
rows. Keep checkpoint files on durable storage and copy them with the run log.

The checkpoint records elapsed time and insert query IDs. Use those IDs in
`system.query_log` to collect `read_rows`, `read_bytes`, `memory_usage`, and
`ProfileEvents['UserTimeMicroseconds'] + ProfileEvents['SystemTimeMicroseconds']`.
Measure background merges separately; query CPU does not include them. Tune
window size and resource limits on the replica before running on a serving node.

## Deployment sequence

The serving cutover is a hard cutover for all projects served by an image.
The schema and capture release must deploy first. Do not deploy the cutover
release until every database it serves has completed backfill and verification.
Rollback requires the previous server image; retain the old table and MVs.

1. Inventory each customer Cloud service, QA service, and multitenant service:
   ClickHouse version, database, source retention, capacity, deletion integration.
2. Apply 048 and verify all five message sources reach both destinations.
3. Wait for inserts started before capture to drain, then start the backfill.
   Keep the old table and both capture MVs throughout the rollout.
4. Revalidate the full historical range. Run a second catch-up checkpoint with
   a later cutoff to cover capture failures and inserts that were in flight.
   Compare representative filtered pages, ordering, retention, and query costs.
5. Deploy the hard-cutover release after all served databases are verified.
   Do not drop `messages` or its five source MVs during this rollout.

Capture is not a transaction across three tables. Monitor MV insert failures
and repeat reconciliation; successful historical validation cannot prove that
future writes will succeed. Operators must also ensure no writer can backdate
`created_at` after the final reconciliation cutoff.

For sharded self-managed installations, run the backfill once per shard with
`--local-tables`, using a separate checkpoint and a direct connection to that
shard. MVs write local tables; content deduplication is shard-local. Replicated
copies of a shard do not need independent backfills. Distributed query coverage
must include cross-shard matches before enabling reads.

Air-gapped rollout uses the same module and migrations packaged with the server.
Deployment-specific packaging, offline upgrade procedures, deletion integration,
maintenance windows, and checkpoint backup locations remain operator checklist
items to fill in before scheduling each customer's migration.
