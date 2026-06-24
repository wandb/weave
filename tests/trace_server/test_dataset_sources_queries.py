"""Functional (ClickHouse-backed) tests for the dataset_sources query builder.

The unit tests in
``tests/trace_server/query_builder/test_dataset_sources_query_builder.py`` assert
the generated SQL *shape*. These tests instead insert real rows into the
``dataset_sources`` table (migration 035) and execute the builder-produced SQL
against ClickHouse, proving the queries actually behave as intended:

- ``make_source_datasets_select`` truncates row_digests with
  ``groupArraySorted(N)`` -> the deterministic N lexicographically-smallest
  digests, alongside the true (un-truncated) ``count()`` total.
- soft-delete: a later tombstone version (higher ``updated_at`` + ``deleted_at``
  set) hides a link from the default reads via the post-collapse ``HAVING``,
  while ``include_deleted=True`` surfaces it; relinking restores it.
- ReplacingMergeTree versions collapse via ``GROUP BY`` + ``argMax(updated_at)``
  with the latest version winning (never ``FINAL``).

ClickHouse-only: the ``ch_server`` fixture skips on the in-memory backend.
"""

from __future__ import annotations

import datetime
from typing import Any

from tests.trace_server.helpers import make_project_id
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.dataset_sources_query_builder import (
    DATASET_SOURCES_INSERT_COLUMNS,
    deterministic_link_id,
    make_dataset_sources_select,
    make_source_datasets_select,
)

_T0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _ts(seconds: int) -> datetime.datetime:
    """A distinct version timestamp; later seconds = later version."""
    return _T0 + datetime.timedelta(seconds=seconds)


def _row(
    *,
    project_id: str,
    dataset_object_id: str,
    row_digest: str,
    source_id: str,
    source_kind: str = "call",
    source_trace_id: str = "trace",
    updated_at: datetime.datetime,
    created_at: datetime.datetime | None = None,
    deleted_at: datetime.datetime = SENTINEL_EPOCH,
    source_display_name: str = "",
) -> list[Any]:
    """One dataset_sources row in DATASET_SOURCES_INSERT_COLUMNS order.

    All versions of a logical key share the deterministic id; ``updated_at``
    distinguishes versions (the ReplacingMergeTree version column).
    """
    link_id = deterministic_link_id(
        project_id,
        dataset_object_id,
        row_digest,
        source_kind,
        source_id,
        source_trace_id,
    )
    return [
        link_id,
        project_id,
        dataset_object_id,
        row_digest,
        source_kind,
        source_id,
        source_trace_id,
        updated_at,  # source_started_at
        source_display_name,
        "",  # link_metadata
        "",  # added_by
        created_at or updated_at,
        updated_at,
        deleted_at,
    ]


def _insert(ch_server: Any, rows: list[list[Any]]) -> None:
    ch_server.ch_client.insert(
        "dataset_sources", rows, column_names=DATASET_SOURCES_INSERT_COLUMNS
    )


def _run(ch_server: Any, query: str, pb: ParamBuilder) -> list[dict[str, Any]]:
    res = ch_server._query(query, parameters=pb.get_params())
    return [dict(zip(res.column_names, row, strict=True)) for row in res.result_rows]


def test_reverse_query_truncates_to_smallest_n_deterministically(
    ch_server: Any,
) -> None:
    """groupArraySorted(N) returns the N lexicographically-smallest digests."""
    project_id = make_project_id("ds_trunc")
    ds = "ds_obj"
    src = ("call", "call_x", "trace_x")

    # Insert 5 digests in NON-sorted order; the builder caps to 3.
    digests = ["row_e", "row_a", "row_d", "row_b", "row_c"]
    _insert(
        ch_server,
        [
            _row(
                project_id=project_id,
                dataset_object_id=ds,
                row_digest=d,
                source_kind=src[0],
                source_id=src[1],
                source_trace_id=src[2],
                updated_at=_ts(i),
            )
            for i, d in enumerate(digests)
        ],
    )

    pb = ParamBuilder()
    query = make_source_datasets_select(
        project_id, [src], pb, include_deleted=False, row_digests_cap=3
    )
    out = _run(ch_server, query, pb)

    assert len(out) == 1
    membership = out[0]
    # Deterministic: the 3 smallest, in sorted order, regardless of insert order.
    assert list(membership["row_digests"]) == ["row_a", "row_b", "row_c"]
    # count() reports the true un-truncated total.
    assert membership["row_digests_total_count"] == 5


def test_forward_query_soft_delete_hidden_then_shown_with_include_deleted(
    ch_server: Any,
) -> None:
    """A later tombstone hides a link by default; include_deleted surfaces it."""
    project_id = make_project_id("ds_softdel")
    ds = "ds_obj"
    common = {
        "project_id": project_id,
        "dataset_object_id": ds,
        "source_id": "call_del",
        "source_trace_id": "trace_del",
    }
    _insert(
        ch_server,
        [
            _row(**common, row_digest="row_deleted", updated_at=_ts(0)),  # live v1
            _row(
                **common,
                row_digest="row_deleted",
                updated_at=_ts(10),
                deleted_at=_ts(10),
            ),  # tombstone v2
            _row(**common, row_digest="row_live", updated_at=_ts(0)),  # live only
        ],
    )

    # Default: the collapsed tombstone is filtered by HAVING; only the live link.
    pb = ParamBuilder()
    out = _run(ch_server, make_dataset_sources_select(project_id, ds, pb), pb)
    assert {r["row_digest"] for r in out} == {"row_live"}

    # include_deleted=True drops the HAVING -> both links present.
    pb2 = ParamBuilder()
    out2 = _run(
        ch_server,
        make_dataset_sources_select(project_id, ds, pb2, include_deleted=True),
        pb2,
    )
    assert {r["row_digest"] for r in out2} == {"row_deleted", "row_live"}


def test_forward_query_relink_after_delete_restores(ch_server: Any) -> None:
    """Live -> tombstone -> relink: the latest (live) version wins after collapse."""
    project_id = make_project_id("ds_restore")
    ds = "ds_obj"
    common = {
        "project_id": project_id,
        "dataset_object_id": ds,
        "row_digest": "row_r",
        "source_id": "call_r",
        "source_trace_id": "trace_r",
    }
    _insert(
        ch_server,
        [
            _row(**common, updated_at=_ts(0)),  # live v1
            _row(**common, updated_at=_ts(10), deleted_at=_ts(10)),  # tombstone v2
            _row(**common, updated_at=_ts(20)),  # relink v3 (live again)
        ],
    )

    pb = ParamBuilder()
    out = _run(ch_server, make_dataset_sources_select(project_id, ds, pb), pb)
    assert {r["row_digest"] for r in out} == {"row_r"}


def test_reverse_query_excludes_soft_deleted(ch_server: Any) -> None:
    """Reverse query drops collapsed-deleted links from row_digests + count."""
    project_id = make_project_id("ds_rev_del")
    ds = "ds_obj"
    src = ("call", "call_rd", "trace_rd")
    common = {
        "project_id": project_id,
        "dataset_object_id": ds,
        "source_kind": src[0],
        "source_id": src[1],
        "source_trace_id": src[2],
    }
    _insert(
        ch_server,
        [
            _row(**common, row_digest="row_1", updated_at=_ts(0)),
            _row(**common, row_digest="row_2", updated_at=_ts(0)),
            _row(
                **common,
                row_digest="row_2",
                updated_at=_ts(10),
                deleted_at=_ts(10),
            ),  # tombstone hides row_2
        ],
    )

    pb = ParamBuilder()
    query = make_source_datasets_select(
        project_id, [src], pb, include_deleted=False, row_digests_cap=100
    )
    out = _run(ch_server, query, pb)
    assert len(out) == 1
    assert list(out[0]["row_digests"]) == ["row_1"]
    assert out[0]["row_digests_total_count"] == 1


def test_forward_query_collapses_versions_latest_payload_wins(ch_server: Any) -> None:
    """Versions collapse to one row; argMax(updated_at) keeps the latest payload."""
    project_id = make_project_id("ds_dedup")
    ds = "ds_obj"
    common = {
        "project_id": project_id,
        "dataset_object_id": ds,
        "row_digest": "row_d",
        "source_id": "call_d",
        "source_trace_id": "trace_d",
    }
    _insert(
        ch_server,
        [
            _row(**common, updated_at=_ts(0), source_display_name="old"),
            _row(**common, updated_at=_ts(10), source_display_name="new"),
        ],
    )

    pb = ParamBuilder()
    out = _run(ch_server, make_dataset_sources_select(project_id, ds, pb), pb)
    assert len(out) == 1  # collapsed to a single logical key
    assert out[0]["source_display_name"] == "new"
