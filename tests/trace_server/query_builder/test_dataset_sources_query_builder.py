"""Unit tests for the dataset_sources query builder (no DB).

Modeled on test_annotation_queues_query_builder.py. These tests assert the
membership-pattern invariants at the SQL-construction level:

- ``deterministic_link_id`` is a stable UUIDv5 over the logical key
  (project_id, dataset_object_id, row_digest, source_kind, source_id,
  source_trace_id): same logical key -> same id; different keys -> different
  ids. source_trace_id is part of the key (a span's identity is
  (trace_id, span_id)).
- The read/state queries dedup via ``GROUP BY`` + ``argMax`` and NEVER use
  ``FINAL`` (FINAL is catastrophically slow at scale).
- All user values are bound via ``ParamBuilder`` (``{pb_N:Type}`` placeholders),
  never string-interpolated.

Each SQL-building test asserts the FULL query shape (whitespace-normalized
equality), not just substring membership, so a change to the generated SQL is
caught here rather than only at the ClickHouse integration layer.
"""

from __future__ import annotations

import uuid

import pytest

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    make_spans_existence_query,
)
from weave.trace_server.query_builder.dataset_sources_query_builder import (
    deterministic_link_id,
    make_dataset_sources_select,
    make_link_state_by_ids_query,
    make_link_state_query,
    make_source_datasets_select,
)


def _norm(sql: str) -> str:
    """Collapse all runs of whitespace to a single space and strip.

    Lets us assert the full query shape without coupling to indentation.
    """
    return " ".join(sql.split())


# The argMax payload projection shared by the forward / link-state reads. The
# version tiebreaker is ``updated_at`` alone (id is constant within a logical
# key, so it can't break a tie).
_PAYLOAD = (
    "argMax(ds.id, ds.updated_at) AS id, "
    "argMax(ds.source_started_at, ds.updated_at) AS source_started_at, "
    "argMax(ds.source_display_name, ds.updated_at) AS source_display_name, "
    "argMax(ds.link_metadata, ds.updated_at) AS link_metadata, "
    "argMax(ds.added_by, ds.updated_at) AS added_by, "
    "argMax(ds.created_at, ds.updated_at) AS created_at, "
    "argMax(ds.updated_at, ds.updated_at) AS updated_at, "
    "argMax(ds.deleted_at, ds.updated_at) AS deleted_at"
)

# Logical key — the GROUP BY for every collapsed read.
_GROUP_BY = (
    "ds.project_id, ds.dataset_object_id, ds.row_digest, "
    "ds.source_kind, ds.source_id, ds.source_trace_id"
)

_KEY_SELECT = (
    "ds.project_id, ds.dataset_object_id, ds.row_digest, "
    "ds.source_kind, ds.source_id, ds.source_trace_id"
)


# ---------------------------------------------------------------------------
# deterministic_link_id
# ---------------------------------------------------------------------------


def test_deterministic_link_id() -> None:
    """Stable for the same logical key, distinct for any field change, UUIDv5.

    Covers D1: source_trace_id is part of the key, so two spans sharing a
    span_id (and content-addressed row_digest) across different traces produce
    distinct ids and must not collapse under ReplacingMergeTree.
    """
    base = {
        "project_id": "proj",
        "dataset_object_id": "ds_obj",
        "row_digest": "row_abc",
        "source_kind": "span",
        "source_id": "span_123",
        "source_trace_id": "trace_abc",
    }

    # Stable: same key -> same id, and it parses as a UUIDv5.
    base_id = deterministic_link_id(**base)
    assert base_id == deterministic_link_id(**base)
    assert uuid.UUID(base_id).version == 5

    # Distinct: changing ANY logical-key field (including source_trace_id, the
    # D1 case) yields a different id, and all variants are mutually distinct.
    variants = [
        {**base, "project_id": "other_proj"},
        {**base, "dataset_object_id": "other_ds"},
        {**base, "row_digest": "row_xyz"},
        {**base, "source_kind": "call"},
        {**base, "source_id": "span_456"},
        {**base, "source_trace_id": "trace_xyz"},
    ]
    ids = {deterministic_link_id(**v) for v in variants}
    assert base_id not in ids
    assert len(ids) == len(variants)


def test_deterministic_link_id_no_delimiter_collision() -> None:
    """Field values containing the join separator must not collide.

    A naive ``"/".join(...)`` of the key fields would map these two distinct
    logical keys to the same string (``a/b/c/...``); the length-prefixed
    encoding keeps them distinct.
    """
    common = {
        "row_digest": "row",
        "source_kind": "span",
        "source_id": "src",
        "source_trace_id": "tr",
    }
    id_1 = deterministic_link_id(project_id="a", dataset_object_id="b/c", **common)
    id_2 = deterministic_link_id(project_id="a/b", dataset_object_id="c", **common)
    assert id_1 != id_2


# ---------------------------------------------------------------------------
# Forward query (dataset -> sources)
# ---------------------------------------------------------------------------


def test_make_dataset_sources_select_sql() -> None:
    project_val = "entity-XYZ/project-XYZ"
    dataset_val = "dataset-object-XYZ"
    pb = ParamBuilder("pb")
    query = make_dataset_sources_select(
        project_id=project_val,
        dataset_object_id=dataset_val,
        pb=pb,
    )

    expected = _norm(
        f"""
        SELECT
            {_KEY_SELECT},
            {_PAYLOAD}
        FROM dataset_sources AS ds
        WHERE ds.project_id = {{pb_0:String}}
            AND ds.dataset_object_id = {{pb_1:String}}
        GROUP BY {_GROUP_BY}
        HAVING deleted_at = toDateTime64(0, 3)
        ORDER BY ds.row_digest ASC, ds.source_kind ASC, ds.source_id ASC,
            ds.source_trace_id ASC
        """
    )
    assert _norm(query) == expected

    # Filter values are bound via ParamBuilder (the placeholders above).
    params = pb.get_params()
    assert params["pb_0"] == project_val
    assert params["pb_1"] == dataset_val


def test_make_dataset_sources_select_with_filters_sql() -> None:
    pb = ParamBuilder("pb")
    query = make_dataset_sources_select(
        project_id="proj",
        dataset_object_id="ds_obj",
        pb=pb,
        row_digests=["row_1", "row_2"],
        source_kinds=["call"],
        limit=10,
        offset=5,
    )

    expected = _norm(
        f"""
        SELECT
            {_KEY_SELECT},
            {_PAYLOAD}
        FROM dataset_sources AS ds
        WHERE ds.project_id = {{pb_0:String}}
            AND ds.dataset_object_id = {{pb_1:String}}
            AND ds.row_digest IN {{pb_2:Array(String)}}
            AND ds.source_kind IN {{pb_3:Array(String)}}
        GROUP BY {_GROUP_BY}
        HAVING deleted_at = toDateTime64(0, 3)
        ORDER BY ds.row_digest ASC, ds.source_kind ASC, ds.source_id ASC,
            ds.source_trace_id ASC
        LIMIT {{pb_4:Int64}}
        OFFSET {{pb_5:Int64}}
        """
    )
    assert _norm(query) == expected

    params = pb.get_params()
    assert params["pb_2"] == ["row_1", "row_2"]
    assert params["pb_3"] == ["call"]
    assert params["pb_4"] == 10
    assert params["pb_5"] == 5


# ---------------------------------------------------------------------------
# Link-state reads (used by link / link_delete write paths)
# ---------------------------------------------------------------------------


def test_make_link_state_query_sql() -> None:
    pb = ParamBuilder("pb")
    query = make_link_state_query(
        project_id="proj",
        dataset_object_id="ds_obj",
        logical_keys=[("row_1", "src_1"), ("row_2", "src_2")],
        pb=pb,
    )

    expected = _norm(
        f"""
        SELECT
            {_KEY_SELECT},
            {_PAYLOAD}
        FROM dataset_sources AS ds
        WHERE ds.project_id = {{pb_0:String}}
            AND ds.dataset_object_id = {{pb_1:String}}
            AND ds.row_digest IN {{pb_2:Array(String)}}
            AND ds.source_id IN {{pb_3:Array(String)}}
        GROUP BY {_GROUP_BY}
        """
    )
    assert _norm(query) == expected

    # row_digests / source_ids are deduped + sorted before binding.
    params = pb.get_params()
    assert params["pb_2"] == ["row_1", "row_2"]
    assert params["pb_3"] == ["src_1", "src_2"]


def test_make_link_state_by_ids_query_sql() -> None:
    pb = ParamBuilder("pb")
    query = make_link_state_by_ids_query(
        project_id="proj",
        link_ids=["id_1", "id_2"],
        pb=pb,
    )

    expected = _norm(
        f"""
        SELECT
            {_KEY_SELECT},
            {_PAYLOAD}
        FROM dataset_sources AS ds
        WHERE ds.project_id = {{pb_0:String}}
            AND ds.id IN {{pb_1:Array(String)}}
        GROUP BY {_GROUP_BY}
        """
    )
    assert _norm(query) == expected

    params = pb.get_params()
    assert params["pb_0"] == "proj"
    assert params["pb_1"] == ["id_1", "id_2"]


# ---------------------------------------------------------------------------
# Reverse query (sources -> datasets)
# ---------------------------------------------------------------------------


def test_make_source_datasets_select_sql_is_two_level_aggregation() -> None:
    project_val = "entity-XYZ/project-XYZ"
    pb = ParamBuilder("pb")
    query = make_source_datasets_select(
        project_id=project_val,
        sources=[("call", "call_123", "trace_abc")],
        pb=pb,
        include_deleted=False,
        row_digests_cap=100,
    )

    # Inner SELECT collapses versions per logical key; outer SELECT regroups by
    # (source_kind, source_id, source_trace_id, dataset_object_id) and caps the
    # row_digests with a deterministic (sorted) truncation.
    expected = _norm(
        """
        SELECT
            source_kind,
            source_id,
            source_trace_id,
            dataset_object_id,
            groupArraySorted(100)(row_digest) AS row_digests,
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
                argMax(ds.created_at, ds.updated_at) AS created_at,
                argMax(ds.deleted_at, ds.updated_at) AS deleted_at
            FROM dataset_sources AS ds
            WHERE ds.project_id = {pb_0:String}
                AND ds.source_id IN {pb_1:Array(String)}
                AND ((ds.source_kind = {pb_2:String} AND ds.source_id = {pb_3:String}
                    AND ds.source_trace_id = {pb_4:String}))
            GROUP BY ds.project_id, ds.dataset_object_id, ds.row_digest,
                ds.source_kind, ds.source_id, ds.source_trace_id
            HAVING deleted_at = toDateTime64(0, 3)
        )
        GROUP BY source_kind, source_id, source_trace_id, dataset_object_id
        ORDER BY source_kind ASC, source_id ASC, source_trace_id ASC,
            dataset_object_id ASC
        """
    )
    assert _norm(query) == expected

    # project_id is bound via ParamBuilder (the placeholder above).
    params = pb.get_params()
    assert params["pb_0"] == project_val


def test_make_source_datasets_select_rejects_empty_sources() -> None:
    pb = ParamBuilder("pb")
    with pytest.raises(ValueError, match="sources must be non-empty"):
        make_source_datasets_select(
            project_id="proj",
            sources=[],
            pb=pb,
            include_deleted=False,
            row_digests_cap=100,
        )


# ---------------------------------------------------------------------------
# Spans existence (agent_query_builder; consumed by the span link path)
# ---------------------------------------------------------------------------


def test_make_spans_existence_query_sql() -> None:
    pb = ParamBuilder("pb")
    query = make_spans_existence_query(
        pb=pb,
        project_id="proj",
        span_keys=[("trace_1", "span_1"), ("trace_2", "span_2")],
    )

    expected = _norm(
        """
        SELECT
            trace_id,
            span_id,
            argMax(spans.span_name, spans.created_at) AS span_name,
            argMax(spans.started_at, spans.created_at) AS started_at
        FROM spans
        WHERE project_id = {pb_0:String}
          AND trace_id IN {pb_1:Array(String)}
          AND span_id IN {pb_2:Array(String)}
        GROUP BY project_id, trace_id, span_id
        """
    )
    assert _norm(query) == expected

    params = pb.get_params()
    assert params["pb_0"] == "proj"
    assert params["pb_1"] == ["trace_1", "trace_2"]
    assert params["pb_2"] == ["span_1", "span_2"]
