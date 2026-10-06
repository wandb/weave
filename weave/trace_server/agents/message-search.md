# Message search storage and rollout

Migration 048 requires ClickHouse 26.2 or later. Upgrade each deployment before
applying it. The query implementation requires 26.3 or later for materialized
CTEs; use the fleet's tested 26.4+ release for rollout.

`messages` remains the ingestion source and rollback read path. Its five
existing span MVs feed two additional MVs:

- `message_content`: one body per `(project_id, content_digest)` after merges,
  with a case-sensitive `text(splitByNonAlpha)` index.
- `message_occurrences`: span metadata, role, timestamp, and content digest.
  Replacement uses `created_at` within the occurrence's full sorting key.

There is no conversation aggregate MV. Identical bodies in different spans
share content but retain distinct occurrences. Content identity uses the
existing 128-bit digest; changing that algorithm would require another migration.

Both tables inherit retention. The content table replaces by the greatest
`expire_at`, retaining a shared body until its longest-lived occurrence expires.
The occurrence table inherits each source row's deadline. Physical removal by
TTL is asynchronous. Historical rows without a deadline retain the existing
2100 default. Project deletion tooling must include both new tables before a
deployment enables capture; content cannot be deleted by a span ID.


## Deploying the migration

The numbered SQL files are discovered by the existing trace-server migrator.
Migration 048 creates empty destination tables and capture MVs; it does not
backfill historical rows. Inserts build the text index immediately.

In core's checked-in `prod-forest` and `zoo-qa` configurations,
`enableInitContainerMigrate: true` runs `python migrator.py` before each
trace-server pod starts. That command applies the latest migrations bundled in
its image. Core must first update its Weave submodule and build and deploy an
image containing 048. Merging the Weave PR alone does not run a migration.

The base chart defaults to no migration hook or init container. Customer and
on-prem installations must use their configured migration job or an explicit
migrator run; these SQL files do not fan out to every ClickHouse instance.
Verify each deployment's migration configuration and ClickHouse version.

Deploy this storage change before deploying indexed reads. Complete and verify
historical backfill separately before the hard cutover. Keep the existing
`messages` table and its five span MVs for capture and rollback.
