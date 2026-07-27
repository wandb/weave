"""Query builder for the dataset_sources membership table.

`dataset_sources` records a membership between dataset rows and their provenance
sources. Shared invariants: deterministic ids, soft-delete tombstones,
idempotent relink, and read-side dedup via GROUP BY + argMax (never FINAL).

This module owns NO SQL against tables it does not own — source-entity
existence/cached-field fetches live in their owners' builders (calls:
``make_queue_add_calls_fetch_calls_query``; spans: ``make_spans_existence_query``).

Every SELECT here collapses ReplacingMergeTree versions with
``GROUP BY <logical key>`` + ``argMax(col, updated_at)`` — NEVER ``FINAL``
(benchmarked ~100x slower). All user-supplied values go through ``ParamBuilder``;
no f-string interpolation of user data.
"""

from __future__ import annotations

import uuid

from weave.trace_server.orm import ParamBuilder

# Stable namespace for deterministic UUIDv5 link ids. UUIDv5 is name-based (a
# hash of namespace + key), so the same logical key always yields the same id —
# that determinism is what makes relink idempotent. v4 (random) and v7
# (time-ordered) are non-deterministic and unusable here.
# Generated once and frozen; changing this would re-key every existing link and
# break idempotent relink.
# The KEY COMPOSITION is frozen too: the set and order of fields hashed into the
# id (see deterministic_link_id) — including source_trace_id — must not change,
# or existing links would re-key.
DATASET_SOURCE_LINK_NAMESPACE = uuid.UUID("9f2c1d3e-7b4a-5c6d-8e9f-0a1b2c3d4e5f")

# Physical column order for INSERTs into dataset_sources. The consumer's link
# and tombstone inserts both build rows in exactly this order, so keep this list
# authoritative.
DATASET_SOURCES_INSERT_COLUMNS = [
    "id",
    "project_id",
    "dataset_object_id",
    "row_digest",
    "source_kind",
    "source_id",
    "source_trace_id",
    "source_started_at",
    "source_display_name",
    "link_metadata",
    "added_by",
    "created_at",
    "updated_at",
    "deleted_at",
]


def deterministic_link_id(
    project_id: str,
    dataset_object_id: str,
    row_digest: str,
    source_kind: str,
    source_id: str,
    source_trace_id: str,
) -> str:
    """Deterministic UUIDv5 over the logical key.

    The logical key
    ``(project_id, dataset_object_id, row_digest, source_kind, source_id,
    source_trace_id)`` uniquely identifies a link independent of its surrogate
    row version. ``source_trace_id`` is part of the key because a span's identity
    is ``(trace_id, span_id)``: two spans sharing a span_id across different
    traces that land on the same content-addressed row_digest are distinct
    edges and must not collapse under ReplacingMergeTree. Because the id is a
    pure function of the logical key, relinking the same key always yields the
    same id (idempotent relink, no read-before-write needed).

    ``source_kind`` is the string enum value ("call" / "span" / "conversation").
    For ``conversation`` and (redundantly) ``call`` the trace is not part of the
    natural identity; callers pass ``""`` for conversation links and the
    call_id-unique value is harmless for calls — the key stays uniform.

    Each field is length-prefixed (``<len>:<value>``) before hashing rather than
    joined by a separator: a value that itself contains the separator (e.g.
    ``project_id`` is ``entity/project``) could otherwise shift a field boundary
    and collide with a different logical key. The length prefix makes the
    encoding injective over the tuple regardless of field contents.
    """
    name = "".join(
        f"{len(part)}:{part}"
        for part in (
            project_id,
            dataset_object_id,
            row_digest,
            source_kind,
            source_id,
            source_trace_id,
        )
    )
    return str(uuid.uuid5(DATASET_SOURCE_LINK_NAMESPACE, name))


# Payload columns selected by argMax-collapsed reads. The aggregation key is the
# logical key, so these are every other column we need to materialize a row.
_ARGMAX_PAYLOAD_COLUMNS = [
    "id",
    "source_started_at",
    "source_display_name",
    "link_metadata",
    "added_by",
    "created_at",
    "updated_at",
    "deleted_at",
]


def _argmax_select(columns: list[str]) -> str:
    """Build ``argMax(ds.col, ds.updated_at) AS col`` per payload column.

    The version tiebreaker is ``updated_at`` alone. ``id`` is a pure function of
    the logical key (the GROUP BY key), so it is identical for every version in
    a group and cannot break a tie — including it in the tiebreaker would be a
    no-op.

    Column references are qualified with the ``ds`` table alias because the
    output aliases (``AS updated_at``, ``AS id``) would otherwise shadow the
    raw columns inside sibling aggregate arguments — ClickHouse rejects that
    with ILLEGAL_AGGREGATION. Qualified references always resolve to the
    table column, never the alias.

    All payload columns are non-nullable: added_by and deleted_at use sentinels
    ('' and the 1970 epoch), not Nullable, so a plain ``argMax(col, ...)`` is
    correct — there are no NULLs for the aggregate to skip, and the latest
    version's value (sentinel included) always wins.
    """
    parts = [f"argMax(ds.{col}, ds.updated_at) AS {col}" for col in columns]
    return ",\n            ".join(parts)


# Logical-key columns, in canonical order. These are the GROUP BY for every read.
# source_trace_id is part of the key (a span's identity is (trace_id, span_id));
# it is last to mirror the table ORDER BY (reads filter via the source_id bloom,
# never trace_id).
_LOGICAL_KEY_COLUMNS = [
    "project_id",
    "dataset_object_id",
    "row_digest",
    "source_kind",
    "source_id",
    "source_trace_id",
]


def make_link_state_query(
    project_id: str,
    dataset_object_id: str,
    logical_keys: list[tuple[str, str]],
    pb: ParamBuilder,
) -> str:
    """Collapsed current state for a set of links being written.

    ``logical_keys`` is a list of ``(row_digest, source_id)`` pairs. We filter on
    the ``row_digest IN (...) AND source_id IN (...)`` supersets (both bounded by
    the request size) and let the caller match exact logical keys in Python —
    this keeps the binding to two array params instead of a per-key OR chain.
    Includes the collapsed ``deleted_at`` and ``created_at`` so the caller can
    compute created/restore status and carry created_at forward.

    Used by dataset_sources_link when include_created_status=True.
    """
    project_param = pb.add(project_id, param_type="String")
    dataset_param = pb.add(dataset_object_id, param_type="String")

    row_digests = sorted({rd for rd, _ in logical_keys})
    source_ids = sorted({sid for _, sid in logical_keys})
    row_digests_param = pb.add(row_digests, param_type="Array(String)")
    source_ids_param = pb.add(source_ids, param_type="Array(String)")

    group_by = ", ".join(f"ds.{c}" for c in _LOGICAL_KEY_COLUMNS)
    payload = _argmax_select(_ARGMAX_PAYLOAD_COLUMNS)

    return f"""
        SELECT
            ds.project_id,
            ds.dataset_object_id,
            ds.row_digest,
            ds.source_kind,
            ds.source_id,
            ds.source_trace_id,
            {payload}
        FROM dataset_sources AS ds
        WHERE ds.project_id = {project_param}
            AND ds.dataset_object_id = {dataset_param}
            AND ds.row_digest IN {row_digests_param}
            AND ds.source_id IN {source_ids_param}
        GROUP BY {group_by}
    """


def make_link_state_by_ids_query(
    project_id: str,
    link_ids: list[str],
    pb: ParamBuilder,
) -> str:
    """Collapsed current state for a set of link ids.

    ``id`` is NOT in the table ORDER BY prefix, so this scans the project's
    partitions filtered by ``id IN (...)``. Delete batches are small, so the
    scan is acceptable. We GROUP BY the logical key (the correct aggregation
    unit) and emit the logical-key columns alongside the payload so callers can
    rebuild a full row to write a tombstone version.

    Used by dataset_sources_link_delete.
    """
    project_param = pb.add(project_id, param_type="String")
    ids_param = pb.add(link_ids, param_type="Array(String)")

    group_by = ", ".join(f"ds.{c}" for c in _LOGICAL_KEY_COLUMNS)
    payload = _argmax_select(_ARGMAX_PAYLOAD_COLUMNS)

    return f"""
        SELECT
            ds.project_id,
            ds.dataset_object_id,
            ds.row_digest,
            ds.source_kind,
            ds.source_id,
            ds.source_trace_id,
            {payload}
        FROM dataset_sources AS ds
        WHERE ds.project_id = {project_param}
            AND ds.id IN {ids_param}
        GROUP BY {group_by}
    """


def make_dataset_sources_select(
    project_id: str,
    dataset_object_id: str,
    pb: ParamBuilder,
    *,
    row_digests: list[str] | None = None,
    source_kinds: list[str] | None = None,
    include_deleted: bool = False,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    """Forward query: dataset -> sources.

    Prefix scan on (project_id, dataset_object_id) with optional row_digest IN
    and source_kind IN narrowing. Collapses versions via GROUP BY logical key +
    argMax. ``include_deleted=False`` filters the COLLAPSED deleted_at via HAVING
    (must run AFTER the argMax so a tombstone version actually hides the link —
    a pre-collapse WHERE on the sentinel would wrongly resurface a link that
    has a live earlier version and a later tombstone).
    """
    project_param = pb.add(project_id, param_type="String")
    dataset_param = pb.add(dataset_object_id, param_type="String")

    where = [
        f"ds.project_id = {project_param}",
        f"ds.dataset_object_id = {dataset_param}",
    ]
    if row_digests is not None:
        rd_param = pb.add(row_digests, param_type="Array(String)")
        where.append(f"ds.row_digest IN {rd_param}")
    if source_kinds is not None:
        sk_param = pb.add(source_kinds, param_type="Array(String)")
        where.append(f"ds.source_kind IN {sk_param}")
    where_sql = " AND ".join(where)

    group_by = ", ".join(f"ds.{c}" for c in _LOGICAL_KEY_COLUMNS)
    payload = _argmax_select(_ARGMAX_PAYLOAD_COLUMNS)

    # HAVING intentionally references the collapsed alias (the argMax output),
    # not the raw column — a tombstone latest-version must hide the link. The
    # 1970-epoch sentinel means "live"; a tombstone has a real deletion time.
    having_sql = "" if include_deleted else "HAVING deleted_at = toDateTime64(0, 3)"

    query = f"""
        SELECT
            ds.project_id,
            ds.dataset_object_id,
            ds.row_digest,
            ds.source_kind,
            ds.source_id,
            ds.source_trace_id,
            {payload}
        FROM dataset_sources AS ds
        WHERE {where_sql}
        GROUP BY {group_by}
        {having_sql}
        ORDER BY ds.row_digest ASC, ds.source_kind ASC, ds.source_id ASC,
            ds.source_trace_id ASC
    """

    if limit is not None:
        limit_param = pb.add(limit, param_type="Int64")
        query += f"\n        LIMIT {limit_param}"
    if offset is not None:
        offset_param = pb.add(offset, param_type="Int64")
        query += f"\n        OFFSET {offset_param}"

    return query


def make_source_datasets_select(
    project_id: str,
    sources: list[tuple[str, str, str]],
    pb: ParamBuilder,
    *,
    include_deleted: bool,
    row_digests_cap: int,
) -> str:
    """Reverse query: sources -> datasets.

    ``sources`` is a list of ``(source_kind, source_id, source_trace_id)``.
    Bloom-assisted: WHERE source_id IN (...) lets ClickHouse skip granules via
    the source_id bloom filter, then we match exact
    (source_kind, source_id, source_trace_id) tuples.

    Two-level aggregation:
      - inner: collapse versions per logical key (argMax deleted_at so the
        tombstone state reflects the latest version, but min(created_at) so the
        earliest write wins). created_at is the earliest write (first_seen), not
        the latest version's value, so blind relinks — which refresh created_at
        to now when include_created_status=False — don't reset it.
        include_deleted=False drops collapsed-deleted rows here.
      - outer: group by (source_kind, source_id, source_trace_id,
        dataset_object_id), capping row_digests at ``row_digests_cap`` and
        reporting the true total + earliest first_seen_at.

    The capped ``row_digests`` use ``groupArraySorted(cap)(row_digest)`` so the
    truncated subset is both deterministic (the N lexicographically-smallest
    digests) and memory-bounded to ``cap`` during aggregation — a bare
    ``groupArray(N)`` keeps an arbitrary N, and ``arraySort(groupArray(...))``
    would materialize the whole set before truncating.
    """
    if not sources:
        raise ValueError("sources must be non-empty")

    project_param = pb.add(project_id, param_type="String")

    source_ids = sorted({sid for _, sid, _ in sources})
    source_ids_param = pb.add(source_ids, param_type="Array(String)")

    # Exact-match tuple set: (source_kind, source_id, source_trace_id).
    # References qualified with the ds alias so the inner SELECT's output
    # aliases cannot shadow them (see _argmax_select docstring).
    tuple_clauses = []
    for kind, sid, trace_id in sources:
        kind_param = pb.add(kind, param_type="String")
        sid_param = pb.add(sid, param_type="String")
        trace_param = pb.add(trace_id, param_type="String")
        tuple_clauses.append(
            f"(ds.source_kind = {kind_param} AND ds.source_id = {sid_param} "
            f"AND ds.source_trace_id = {trace_param})"
        )
    exact_match_sql = " OR ".join(tuple_clauses)

    group_by_inner = ", ".join(f"ds.{c}" for c in _LOGICAL_KEY_COLUMNS)
    # HAVING intentionally references the collapsed alias (argMax output).
    inner_having = "" if include_deleted else "HAVING deleted_at = toDateTime64(0, 3)"

    # groupArraySorted(N) requires N as a parametric literal (not a query-bound
    # parameter). row_digests_cap is a server-controlled constant
    # (MAX_ROW_DIGESTS_PER_RESULT), never user input, so coerce to a bounded
    # int and inline it.
    cap_literal = int(row_digests_cap)
    if cap_literal < 1:
        raise ValueError(f"row_digests_cap must be >= 1, got {row_digests_cap!r}")

    return f"""
        SELECT
            source_kind,
            source_id,
            source_trace_id,
            dataset_object_id,
            groupArraySorted({cap_literal})(row_digest) AS row_digests,
            count() AS row_digests_total_count,
            min(created_at) AS first_seen_at
        FROM (
            SELECT
                ds.project_id,
                ds.dataset_object_id,
                ds.row_digest,
                ds.source_kind,
                ds.source_id,
                ds.source_trace_id,
                min(ds.created_at) AS created_at,
                argMax(ds.deleted_at, ds.updated_at) AS deleted_at
            FROM dataset_sources AS ds
            WHERE ds.project_id = {project_param}
                AND ds.source_id IN {source_ids_param}
                AND ({exact_match_sql})
            GROUP BY {group_by_inner}
            {inner_having}
        )
        GROUP BY source_kind, source_id, source_trace_id, dataset_object_id
        ORDER BY source_kind ASC, source_id ASC, source_trace_id ASC,
            dataset_object_id ASC
    """


__all__ = [
    "DATASET_SOURCES_INSERT_COLUMNS",
    "DATASET_SOURCE_LINK_NAMESPACE",
    "deterministic_link_id",
    "make_dataset_sources_select",
    "make_link_state_by_ids_query",
    "make_link_state_query",
    "make_source_datasets_select",
]
