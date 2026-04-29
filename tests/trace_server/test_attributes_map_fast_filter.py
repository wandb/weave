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

TEST_ENTITY = "attrs_fast_filter_entity"


@pytest.fixture
def ch_server_force_legacy(
    clickhouse_trace_server: ClickHouseTraceServer,
) -> ClickHouseTraceServer:
    """Reuse the global ``clickhouse_trace_server`` fixture but pin FORCE_LEGACY.

    This test inserts directly into ``call_parts`` (bypassing the v2 write
    path) so reads must go through ``calls_merged``. The shared fixture
    defaults to AUTO, which would route reads to ``calls_complete`` and
    miss the raw-inserted rows.
    """
    clickhouse_trace_server.table_routing_resolver._mode = (
        CallsStorageServerMode.FORCE_LEGACY
    )
    reset_project_residence_cache()
    return clickhouse_trace_server


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


def _populate_two_by_two(
    ch_client: object,
    internal_project_id: str,
    attr_key: str,
    matching_value: object,
    other_value: object,
    now: datetime.datetime,
) -> tuple[str, str, str, str]:
    """Insert the four-row fixture: populated+match, legacy+match, populated+other, legacy+other.

    Returns the call ids in that order so tests can assert membership. All
    rows share a project; the assertion is that only the two "match" rows
    come back regardless of backfill state.
    """
    call_populated_match = str(uuid.uuid4())
    call_legacy_match = str(uuid.uuid4())
    call_populated_other = str(uuid.uuid4())
    call_legacy_other = str(uuid.uuid4())
    _insert_start_row(
        ch_client,
        internal_project_id,
        call_populated_match,
        now,
        {attr_key: matching_value},
        populate_typed_maps=True,
    )
    _insert_start_row(
        ch_client,
        internal_project_id,
        call_legacy_match,
        now + datetime.timedelta(seconds=1),
        {attr_key: matching_value},
        populate_typed_maps=False,
    )
    _insert_start_row(
        ch_client,
        internal_project_id,
        call_populated_other,
        now + datetime.timedelta(seconds=2),
        {attr_key: other_value},
        populate_typed_maps=True,
    )
    _insert_start_row(
        ch_client,
        internal_project_id,
        call_legacy_other,
        now + datetime.timedelta(seconds=3),
        {attr_key: other_value},
        populate_typed_maps=False,
    )
    return (
        call_populated_match,
        call_legacy_match,
        call_populated_other,
        call_legacy_other,
    )


@pytest.mark.parametrize(
    ("attr_key", "matching_value", "other_value", "cast_to"),
    [
        # The hybrid ``if(mapContains(...))`` wins on the populated row and
        # falls back to ``toString(coalesce(nullIf(JSON_VALUE, 'null'), ''))``
        # on the legacy row whose typed maps are empty.
        ("env", "prod", "staging", "string"),
        ("retries", 5, 2, "int"),
        ("score", 0.9, 0.1, "double"),
        # bool is the case that would have failed before we special-cased it:
        # the bool fallback compares the raw JSON_VALUE to ``'true'`` rather
        # than going through the generic ``toUInt8OrNull`` cast (which returns
        # NULL on the JSON bool strings ``"true"``/``"false"`` and would drop
        # legacy rows with ``enabled: true`` in the dump).
        ("enabled", True, False, "bool"),
    ],
    ids=["string", "int", "double", "bool"],
)
def test_fast_filter_mixed_backfill_convert(
    trace_server: object,
    ch_server_force_legacy: ClickHouseTraceServer,
    attr_key: str,
    matching_value: object,
    other_value: object,
    cast_to: str,
) -> None:
    """``$convert(attributes.<key>, <cast>)`` returns populated *and* legacy matches.

    Both the typed-map row and the JSON_VALUE-only legacy row come back; the
    "other" rows don't. Pinned per-cast so a regression in any one type's
    fallback (especially bool) surfaces independently.
    """
    external_project_id = f"{TEST_ENTITY}/{cast_to}_{uuid.uuid4().hex[:8]}"
    internal_project_id = b64(external_project_id)
    reset_project_residence_cache()
    populated_match, legacy_match, *_ = _populate_two_by_two(
        ch_server_force_legacy.ch_client,
        internal_project_id,
        attr_key=attr_key,
        matching_value=matching_value,
        other_value=other_value,
        now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0),
    )

    matching_ids = _query_ids(
        trace_server,
        external_project_id,
        {
            "$eq": [
                {
                    "$convert": {
                        "input": {"$getField": f"attributes.{attr_key}"},
                        "to": cast_to,
                    }
                },
                {"$literal": matching_value},
            ]
        },
    )
    assert matching_ids == {populated_match, legacy_match}


def test_fast_filter_mixed_backfill_implicit_string_no_convert(
    trace_server: object,
    ch_server_force_legacy: ClickHouseTraceServer,
) -> None:
    """``attributes.env = 'prod'`` (no ``$convert``) matches populated + legacy.

    Covers the implicit-string fast path: when the peer is a string
    ``$literal``, the query builder routes through ``attributes_map_str``
    without requiring the caller to wrap in ``$convert(..., "string")``.
    The row-level ``mapContains`` guard still gates the fast read so the
    legacy row falls back to the JSON_VALUE branch and matches.
    """
    external_project_id = f"{TEST_ENTITY}/implicit_string_{uuid.uuid4().hex[:8]}"
    internal_project_id = b64(external_project_id)
    reset_project_residence_cache()
    populated_match, legacy_match, *_ = _populate_two_by_two(
        ch_server_force_legacy.ch_client,
        internal_project_id,
        attr_key="env",
        matching_value="prod",
        other_value="staging",
        now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0),
    )

    matching_ids = _query_ids(
        trace_server,
        external_project_id,
        {
            "$eq": [
                {"$getField": "attributes.env"},
                {"$literal": "prod"},
            ]
        },
    )
    assert matching_ids == {populated_match, legacy_match}


def test_fast_filter_missing_int_key_does_not_match_map_default(
    trace_server: object,
    ch_server_force_legacy: ClickHouseTraceServer,
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
        ch_server_force_legacy.ch_client,
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
        ch_server_force_legacy.ch_client,
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
        ch_server_force_legacy.ch_client,
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
