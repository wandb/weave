# The Membership Pattern

This document captures the shared invariants for the "membership" pattern: a
ClickHouse table that records a many-to-many relationship between two domain
entities, with soft-delete and idempotent relink semantics.

Current instances:

1. `annotation_queue_items` (migration 023) — calls ↔ annotation queues
2. `dataset_sources` (migration 034) — dataset rows ↔ provenance sources
   (a "source" is a Weave call or an agent span)

> **STOP if you are adding a third instance.** Two instances is a coincidence;
> three is a pattern that deserves a shared contract. Before adding a third
> sibling table, design shared types/invariants (see "One contract, N tables"
> below). Do **not** generalize prematurely off of two.

## Logical key

Every membership row has a **logical key** — the tuple that uniquely identifies
the relationship independent of the row's surrogate `id`.

- `dataset_sources`: `(project_id, dataset_object_id, row_digest, source_kind, source_id)`
- `annotation_queue_items`: `(project_id, queue_id, call_id)`

Link `id`s are **deterministic** — a UUIDv5 computed over the logical key. This
is what makes relink idempotent (same logical key → same `id`) without a
read-before-write.

## Cached-field snapshot semantics

Membership rows cache display/sort fields from the source entity (e.g.
`source_display_name`, `source_started_at`, `source_trace_id` on
`dataset_sources`). These are **snapshotted at link time and never refreshed**.

They exist so the relationship can still be rendered after the source entity is
hard-deleted — i.e. to display "orphan" links. They are explicitly **not** a
source of truth for the current state of the source entity. Do not add refresh
logic; if a consumer needs live source data it must join against the source
table itself.

## Soft-delete

Deletion is a **tombstone**: set `deleted_at` to a non-NULL timestamp on a new
version of the row (via the ReplacingMergeTree `updated_at` version). There is
**no cascade** — deleting a source entity does not delete its membership rows
(that is precisely why cached fields exist).

Read queries filter `deleted_at IS NULL` unless `include_deleted` is requested.

## Idempotent relink

Because the `id` is deterministic over the logical key:

- Linking the same logical key twice yields the **same** `id` (no duplicate).
- Relinking after a soft-delete **restores** the row by writing a new version
  with `deleted_at = NULL`.

### `created_at` carry-forward divergence (status-checked vs blind relinks)

`dataset_sources_link` takes an `include_created_status` flag. When it is
**True**, the endpoint runs a pre-insert lookup of current link state; for any
logical key that already has a version (live *or* tombstoned), the prior row's
`created_at` is **carried forward** into the new version so `first_seen`
semantics are preserved across relinks and restores, and the entry reports
`created=False`. When it is **False** (a *blind* relink), no lookup runs: the
endpoint cannot know a prior `created_at`, so every written version gets
`created_at = now` (created_at is **refreshed**), and the entry reports
`created=None` ("not requested"). Callers that care about a stable first-seen
timestamp must therefore pass `include_created_status=True`. Both backends
(ClickHouse insert-only + read-side argMax; SQLite upsert) implement this
identical divergence.

## Read-side dedup — NEVER use FINAL

ReplacingMergeTree only merges duplicate versions eventually, in the background.
Reads must dedup explicitly:

```sql
GROUP BY <logical key>
... argMax(col, (updated_at, id)) ...
```

`argMax` over `(updated_at, id)` picks the latest version. The `id` tiebreaker
only disambiguates rows with *different* logical keys that race in the same
instant; it can NOT break ties between two versions of the *same* link, because
deterministic ids mean those versions share the id. That is why `updated_at`
is `DateTime64(6)`: microsecond precision makes sequential operations (e.g.
delete then relink, two separate server roundtrips) always produce distinct
versions. Only truly concurrent writes to the same link can tie at the
microsecond, and there either outcome is acceptable — the operations were
unordered.

**Do not use `FINAL`.** It was benchmarked and is catastrophically slow at
scale: the reverse query went from ~20ms (GROUP BY + argMax) to ~1.9s (FINAL)
at 100M rows. `FINAL` forces a full merge at query time; `GROUP BY` + `argMax`
does the dedup in the aggregation we already need.

## One contract, N tables

When the third instance appears, share the **types and invariants** (logical
key derivation, soft-delete, deterministic id, dedup query shape) — do **not**
collapse the instances into one mega-table.

Each consumer needs a different physical `ORDER BY` for its dominant query
direction (forward vs reverse), and different cached fields. A shared table
would force a compromise sort order that is slow for everyone. Share the
behavior, not the storage.
