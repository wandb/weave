# Message search storage and rollout

## Serving cutover

The trace server always uses the indexed query for every project's message
search. There is no project allowlist or environment-variable switch. The
serving path resolves occurrence versions with `FINAL`; the builder's
`stable_metadata` option is available for experiments only.

Complete capture verification and historical backfill for every database served
by a release before deploying the cutover code. Schema migration alone does not
copy history. Deploy storage and capture first, run and reconcile the backfill,
then deploy the query cutover as a separate release. Rollback requires deploying
the previous server image; retain the old table and its ingestion MVs.

## Query contract

The indexed builder uses case-sensitive complete words in any order. Double
quotes require consecutive tokens, so `warm "acoustic guitar"` requires both
the word `warm` and the phrase. Tokenizer punctuation is ignored, including
Markdown emphasis. This does not strip Markdown syntax or render link labels;
URLs, code, and markup remain searchable. Substrings and case folding are not
part of this contract. Unclosed quotes and punctuation-only queries are errors.

The request and response shapes are unchanged. An empty query remains structured
retrieval: it returns each logical span occurrence and honors `truncate_content`.
Text search collapses identical `(role, content_digest)` matches within a
conversation, falling back to trace ID and then span ID when untagged. It keeps
the newest occurrence inside the requested time window. Offsets and limits apply
to those message hits, not the number of conversation groups in the response.

One SQL statement finds digest candidates using the text index, selects the
ordered occurrence page, and joins bodies only for that materialized page.
`GLOBAL IN` and `GLOBAL JOIN` preserve cross-shard matching. Content hydration
groups digests so unmerged duplicate bodies cannot multiply results.

The default query uses `FINAL` on occurrences before metadata filtering. The
`stable_metadata` option removes it and uses one ordered collapse, matching the
fast benchmark query. Enable that option only when an occurrence's conversation
ID and all filter metadata stay unchanged across exports. Empty-to-known
conversation IDs violate that condition. Otherwise old versions can return
stale matches, duplicate a message across conversations, and consume page slots.
Ingestion currently permits such updates, so the optimization is opt-in.

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

See [the backfill runbook](message-search-backfill.md) for the resumable command,
verification, and deployment sequence.
