"""Unit tests for the dataset_sources query builder (no DB).

Modeled on test_annotation_queues_query_builder.py. These tests assert the
membership-pattern invariants at the SQL-construction level:

- ``deterministic_link_id`` is a stable UUIDv5 over the logical key
  (project_id, dataset_object_id, row_digest, source_kind, source_id,
  source_trace_id): same logical key -> same id; different keys -> different
  ids. source_trace_id is part of the key (a span's identity is
  (trace_id, span_id)).
- The read queries (forward + reverse) dedup via ``GROUP BY`` + ``argMax``
  and NEVER use ``FINAL`` (FINAL is catastrophically slow at scale).
- All user values are bound via ``ParamBuilder`` (``{pb_N: Type}`` placeholders),
  never string-interpolated.

NOTE: this imports from
``weave.trace_server.query_builder.dataset_sources_query_builder``, which is
authored by Task B. If that module / these symbols do not exist yet, this file
will fail to COLLECT -- that is the expected TDD state until Task B lands.
"""

from __future__ import annotations

import uuid

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.dataset_sources_query_builder import (
    deterministic_link_id,
    make_dataset_sources_select,
    make_source_datasets_select,
)

# ---------------------------------------------------------------------------
# deterministic_link_id
# ---------------------------------------------------------------------------


def test_deterministic_link_id_is_stable_for_same_logical_key() -> None:
    key = {
        "project_id": "proj",
        "dataset_object_id": "ds_obj",
        "row_digest": "row_abc",
        "source_kind": "span",
        "source_id": "span_123",
        "source_trace_id": "trace_abc",
    }
    id_a = deterministic_link_id(**key)
    id_b = deterministic_link_id(**key)
    assert id_a == id_b


def test_deterministic_link_id_distinct_for_different_keys() -> None:
    base = {
        "project_id": "proj",
        "dataset_object_id": "ds_obj",
        "row_digest": "row_abc",
        "source_kind": "span",
        "source_id": "span_123",
        "source_trace_id": "trace_abc",
    }
    base_id = deterministic_link_id(**base)

    # Each field that participates in the logical key must change the id.
    variants = [
        {**base, "project_id": "other_proj"},
        {**base, "dataset_object_id": "other_ds"},
        {**base, "row_digest": "row_xyz"},
        {**base, "source_kind": "call"},
        {**base, "source_id": "span_456"},
        # source_trace_id is part of the key: two spans sharing span_id across
        # different traces are distinct edges (D1).
        {**base, "source_trace_id": "trace_xyz"},
    ]
    ids = {deterministic_link_id(**v) for v in variants}
    assert base_id not in ids
    # All variants are mutually distinct too.
    assert len(ids) == len(variants)


def test_deterministic_link_id_same_span_id_distinct_traces_differ() -> None:
    # The motivating case for D1: same span_id, same content-addressed
    # row_digest, different trace -> distinct links (must not collapse under
    # ReplacingMergeTree).
    common = {
        "project_id": "proj",
        "dataset_object_id": "ds_obj",
        "row_digest": "row_abc",
        "source_kind": "span",
        "source_id": "span_dup",
    }
    id_trace_1 = deterministic_link_id(**common, source_trace_id="trace_1")
    id_trace_2 = deterministic_link_id(**common, source_trace_id="trace_2")
    assert id_trace_1 != id_trace_2


def test_deterministic_link_id_is_a_uuid_string() -> None:
    link_id = deterministic_link_id(
        project_id="proj",
        dataset_object_id="ds_obj",
        row_digest="row_abc",
        source_kind="conversation",
        source_id="conv_123",
        source_trace_id="",
    )
    # Must parse as a UUID (UUIDv5 over the logical key).
    parsed = uuid.UUID(str(link_id))
    assert parsed.version == 5


# ---------------------------------------------------------------------------
# Forward query (dataset -> sources)
# ---------------------------------------------------------------------------


def test_make_dataset_sources_select_dedups_via_group_by_argmax_no_final() -> None:
    # Use distinctive values that do NOT collide with column-name substrings
    # (e.g. "project_id" contains "proj"), so the "not interpolated" assertion
    # is meaningful.
    project_val = "entity-XYZ/project-XYZ"
    dataset_val = "dataset-object-XYZ"
    pb = ParamBuilder("pb")
    query = make_dataset_sources_select(
        project_id=project_val,
        dataset_object_id=dataset_val,
        pb=pb,
    )
    params = pb.get_params()
    normalized = " ".join(query.split()).lower()

    # Read-side dedup: GROUP BY + argMax, NEVER FINAL.
    assert "group by" in normalized
    assert "argmax" in normalized
    assert "final" not in normalized

    # Values are bound via ParamBuilder, not string-interpolated.
    assert project_val not in query
    assert dataset_val not in query
    assert project_val in params.values()
    assert dataset_val in params.values()


def test_make_dataset_sources_select_filters_use_param_builder() -> None:
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
    params = pb.get_params()
    param_values = list(params.values())

    # All filter values are bound via ParamBuilder, not string-interpolated.
    assert "row_1" not in query
    assert "row_2" not in query
    assert ["row_1", "row_2"] in param_values or (
        "row_1" in param_values and "row_2" in param_values
    )
    assert 10 in param_values
    assert 5 in param_values


def test_make_dataset_sources_select_excludes_deleted_by_default() -> None:
    pb = ParamBuilder("pb")
    query = make_dataset_sources_select(
        project_id="proj",
        dataset_object_id="ds_obj",
        pb=pb,
    )
    normalized = " ".join(query.split()).lower()
    # Default filters out tombstoned rows (post-collapse, via HAVING). deleted_at
    # is a sentinel-epoch column (not Nullable), so "live" is `= toDateTime64(0)`.
    assert "having deleted_at = todatetime64(0, 3)" in normalized


# ---------------------------------------------------------------------------
# Reverse query (sources -> datasets)
# ---------------------------------------------------------------------------


def test_make_source_datasets_select_dedups_via_group_by_argmax_no_final() -> None:
    project_val = "entity-XYZ/project-XYZ"
    pb = ParamBuilder("pb")
    query = make_source_datasets_select(
        project_id=project_val,
        sources=[("call", "call_123", "trace_abc")],
        pb=pb,
        include_deleted=False,
        row_digests_cap=100,
    )
    params = pb.get_params()
    normalized = " ".join(query.split()).lower()

    assert "group by" in normalized
    assert "argmax" in normalized
    assert "final" not in normalized

    # Source id, trace id, and project id are bound, not interpolated.
    assert "call_123" not in query
    assert "trace_abc" not in query
    assert project_val not in query
    assert project_val in params.values()
