"""End-to-end test for the attributes_map_* fast-filter path on ClickHouse.

Migration 030 adds typed ``attributes_map_*`` columns that ``extract_typed_attrs``
populates at ingest. Legacy rows inserted before the migration ran (or before
a backfill job reaches them) have empty maps, so a naive ``map[key]`` lookup
would return the CH value-type default and silently miss legitimate matches.

The query builder emits ``if(mapContains(map, key), map[key], JSON_VALUE(...))``
per row; this test pins that contract end-to-end by raw-inserting three rows
into ``call_parts`` with different ingest states and asserting the
``calls_query_stream`` results:

  - populated   : typed maps set at ingest (post-migration)
  - legacy      : attributes_dump only, typed maps empty (pre-migration)
  - negative    : attributes_dump mismatch (must not match, regardless of maps)

Mixed inserts in the same project cover the partial-backfill scenario the
reviewer flagged on #6678.
"""

from __future__ import annotations

import datetime
import json
import uuid

import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import b64
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_schema import EXPIRE_AT_NEVER
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.project_version.project_version import (
    reset_project_residence_cache,
)
from weave.trace_server.project_version.types import CallsStorageServerMode
from weave.trace_server.sqlite_trace_server import SqliteTraceServer

TEST_ENTITY = "attrs_fast_filter_entity"


@pytest.fixture
def clickhouse_trace_server(trace_server: object) -> ClickHouseTraceServer:
    """Return the internal CH server; skip on SQLite.

    Force FORCE_LEGACY routing so reads hit calls_merged — this test inserts
    directly into call_parts, not calls_complete, so we want the merged view.
    """
    internal = trace_server._internal_trace_server  # type: ignore[attr-defined]
    if isinstance(internal, SqliteTraceServer):
        pytest.skip("ClickHouse-only test")
    internal.table_routing_resolver._mode = CallsStorageServerMode.FORCE_LEGACY
    reset_project_residence_cache()
    return internal


# Columns populated on a call_parts start row. Kept as a list so ch_client.insert
# can enforce positional order with the value rows below.
_START_COLUMNS = [
    "project_id",
    "id",
    "trace_id",
    "parent_id",
    "op_name",
    "started_at",
    "attributes_dump",
    "attributes_map_str",
    "attributes_map_int",
    "attributes_map_float",
    "attributes_map_bool",
    "inputs_dump",
    "input_refs",
    "output_refs",
    "expire_at",
]


def _insert_start_row(
    ch_client: object,
    project_id: str,
    call_id: str,
    started_at: datetime.datetime,
    attributes: dict[str, object],
    *,
    populate_typed_maps: bool,
) -> None:
    """Raw-insert one call_parts start row with optional typed-map population.

    ``populate_typed_maps=False`` simulates a legacy pre-migration row: the
    attributes dict is written to ``attributes_dump`` only and the four typed
    maps remain empty ``{}``. ``populate_typed_maps=True`` mirrors what
    ``extract_typed_attrs`` would do at ingest for rows the feature sees.
    """
    attrs_str: dict[str, str] = {}
    attrs_int: dict[str, int] = {}
    attrs_float: dict[str, float] = {}
    attrs_bool: dict[str, bool] = {}
    if populate_typed_maps:
        for k, v in attributes.items():
            # Match extract_typed_attrs dispatch: bool before int (bool ⊂ int).
            if isinstance(v, bool):
                attrs_bool[k] = v
            elif isinstance(v, int):
                attrs_int[k] = v
            elif isinstance(v, float):
                attrs_float[k] = v
            elif isinstance(v, str):
                attrs_str[k] = v

    ch_client.insert(  # type: ignore[attr-defined]
        "call_parts",
        [
            [
                project_id,
                call_id,
                str(uuid.uuid4()),
                "",
                "test_op",
                started_at,
                json.dumps(attributes),
                attrs_str,
                attrs_int,
                attrs_float,
                attrs_bool,
                "{}",
                [],
                [],
                EXPIRE_AT_NEVER,
            ]
        ],
        column_names=_START_COLUMNS,
    )


def _query_ids(trace_server: object, project_id: str, filter_query: dict) -> set[str]:
    """Return the set of call ids returned by a filtered calls_query_stream."""
    calls = list(
        trace_server.calls_query_stream(  # type: ignore[attr-defined]
            tsi.CallsQueryReq(project_id=project_id, query={"$expr": filter_query})
        )
    )
    return {c.id for c in calls}


@pytest.mark.parametrize(
    ("cast", "attr_key", "filter_literal", "matching_value", "other_value"),
    [
        ("string", "env", "prod", "prod", "staging"),
        ("int", "retries", 5, 5, 2),
        ("double", "score", 0.9, 0.9, 0.1),
        # bool is intentionally excluded: the JSON_VALUE fallback cast is
        # ``toUInt8OrNull``, which returns NULL for the string ``"true"``
        # that JSON_VALUE emits for a JSON bool. That preexisting fallback
        # limitation means legacy bool rows can't be recovered via the dump,
        # independent of this hybrid path.
    ],
)
def test_fast_filter_mixed_backfill_returns_correct_rows(
    trace_server: object,
    clickhouse_trace_server: ClickHouseTraceServer,
    cast: str,
    attr_key: str,
    filter_literal: object,
    matching_value: object,
    other_value: object,
) -> None:
    """``$convert`` filter must return both populated and legacy rows that match.

    Four rows per type go into one project: two match the filter (populated
    + legacy), two don't (populated + legacy with a different value). The
    hybrid ``if(mapContains(...))`` path is the only thing that can return
    the legacy-matching row — a pure Map read would miss it because the
    map is empty and the CH default for the value type is used instead.
    """
    external_project_id = f"{TEST_ENTITY}/{cast}_{uuid.uuid4().hex[:8]}"
    internal_project_id = b64(external_project_id)
    reset_project_residence_cache()

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    call_populated_match = str(uuid.uuid4())
    call_legacy_match = str(uuid.uuid4())
    call_populated_other = str(uuid.uuid4())
    call_legacy_other = str(uuid.uuid4())

    # Populated row that matches the filter.
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_populated_match,
        now,
        {attr_key: matching_value},
        populate_typed_maps=True,
    )
    # Legacy row that matches the filter (typed maps empty, dump has the key).
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_legacy_match,
        now + datetime.timedelta(seconds=1),
        {attr_key: matching_value},
        populate_typed_maps=False,
    )
    # Populated row that doesn't match.
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_populated_other,
        now + datetime.timedelta(seconds=2),
        {attr_key: other_value},
        populate_typed_maps=True,
    )
    # Legacy row that doesn't match.
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_legacy_other,
        now + datetime.timedelta(seconds=3),
        {attr_key: other_value},
        populate_typed_maps=False,
    )

    matching_ids = _query_ids(
        trace_server,
        external_project_id,
        {
            "$eq": [
                {
                    "$convert": {
                        "input": {"$getField": f"attributes.{attr_key}"},
                        "to": cast,
                    }
                },
                {"$literal": filter_literal},
            ]
        },
    )

    assert matching_ids == {call_populated_match, call_legacy_match}, (
        f"cast={cast}: expected both populated and legacy matching rows; "
        f"got {matching_ids}"
    )


def test_fast_filter_missing_int_key_does_not_match_map_default(
    trace_server: object,
    clickhouse_trace_server: ClickHouseTraceServer,
) -> None:
    """Without the mapContains gate, ``attributes.missing = 0`` would match every
    populated row — ClickHouse returns ``0`` for a missing Int64 Map key. The
    ``if(mapContains(...))`` wrapper ensures we instead fall through to the
    JSON_VALUE path, which yields NULL for a missing JSON key and does not
    compare equal to ``0``.

    This is the concrete failure mode the reviewer warned about on #6678:
    a partially-backfilled table (or a row whose particular attribute never
    existed) silently looking like it holds the zero value. The filter must
    not match either populated-but-missing or legacy rows.
    """
    external_project_id = f"{TEST_ENTITY}/missing_int_{uuid.uuid4().hex[:8]}"
    internal_project_id = b64(external_project_id)
    reset_project_residence_cache()
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

    # Populated row: attribute exists, but *not* the one we'll filter on.
    # mapContains('missing_key') must be false, so the Int64 Map default (0)
    # cannot leak into the comparison.
    call_populated_missing_key = str(uuid.uuid4())
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_populated_missing_key,
        now,
        {"unrelated": 42},
        populate_typed_maps=True,
    )
    # Legacy row with nothing in the typed maps either — fallback must also
    # not match, because the JSON path for a missing key is NULL.
    call_legacy_missing_key = str(uuid.uuid4())
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_legacy_missing_key,
        now + datetime.timedelta(seconds=1),
        {"unrelated": 42},
        populate_typed_maps=False,
    )
    # Control: a populated row that actually has the attribute set to 0.
    # This one *should* match, proving the filter itself is wired up.
    call_populated_zero = str(uuid.uuid4())
    _insert_start_row(
        clickhouse_trace_server.ch_client,
        internal_project_id,
        call_populated_zero,
        now + datetime.timedelta(seconds=2),
        {"counter": 0},
        populate_typed_maps=True,
    )

    matching_ids = _query_ids(
        trace_server,
        external_project_id,
        {
            "$eq": [
                {
                    "$convert": {
                        "input": {"$getField": "attributes.counter"},
                        "to": "int",
                    }
                },
                {"$literal": 0},
            ]
        },
    )
    assert matching_ids == {call_populated_zero}, (
        "Only the populated row whose 'counter' is actually 0 should match; "
        f"the missing-key rows must not leak the Map default. got {matching_ids}"
    )
