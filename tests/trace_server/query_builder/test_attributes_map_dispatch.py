"""Tests for the typed attributes-map fast-filter dispatch.

When a caller filters on ``attributes.<path>`` with an explicit ``$convert``
cast, the query builder emits a hybrid
``if(mapContains(map, key), map[key], clickhouse_cast(JSON_VALUE(...)))``
expression: the typed Map column wins on rows where migration 030 populated
it at ingest, and the old JSON_VALUE path takes over on legacy rows whose
maps are still empty. This file asserts the full SQL shape end-to-end on
both read tables plus the fall-through cases (no cast, ``exists`` cast).

Each test is intentionally un-parametrized and pins the complete query
shape — the SQL layer is load-bearing enough that a shared template or
fuzzy match would miss regressions at the punctuation level.
"""

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.clickhouse.utilities import (
    MAX_TYPED_ATTR_ENTRIES_PER_MAP,
    extract_typed_attrs,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.project_version.types import ReadTable

# ---------------------------------------------------------------------------
# calls_merged dispatch (one test per supported cast)
# ---------------------------------------------------------------------------


def test_typed_map_dispatch_on_calls_merged_int() -> None:
    """``$convert(attributes.env, int)`` on calls_merged.

    Fast branch: ``any(attributes_map_int)[key]``.
    Fallback: ``toInt64OrNull(coalesce(nullIf(JSON_VALUE(...), 'null'), ''))``.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.env"},
                            "to": "int",
                        }
                    },
                    {"$literal": 1},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((if(mapContains(any(calls_merged.attributes_map_int), {pb_0:String}),
                 any(calls_merged.attributes_map_int)[{pb_0:String}],
                 toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:Int64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "env", "pb_1": '$."env"', "pb_2": 1, "pb_3": "p"},
    )


def test_typed_map_dispatch_on_calls_merged_double() -> None:
    """``$convert(attributes.env, double)`` on calls_merged.

    Fast branch: ``any(attributes_map_float)[key]``.
    Fallback: ``toFloat64OrNull(coalesce(nullIf(JSON_VALUE(...), 'null'), ''))``.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.env"},
                            "to": "double",
                        }
                    },
                    {"$literal": 1.5},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((if(mapContains(any(calls_merged.attributes_map_float), {pb_0:String}),
                 any(calls_merged.attributes_map_float)[{pb_0:String}],
                 toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:Float64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "env", "pb_1": '$."env"', "pb_2": 1.5, "pb_3": "p"},
    )


def test_typed_map_dispatch_on_calls_merged_bool() -> None:
    """``$convert(attributes.env, bool)`` on calls_merged.

    Fast branch: ``any(attributes_map_bool)[key]``.
    Fallback: ``(JSON_VALUE(...) = 'true')`` — bool is special-cased because
    ``JSON_VALUE`` emits the literal string ``"true"``/``"false"`` for JSON
    booleans and the generic ``toUInt8OrNull`` cast returns NULL on those
    strings, which would silently drop legacy bool rows. Comparing the raw
    JSON_VALUE to ``'true'`` yields a Bool directly.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.env"},
                            "to": "bool",
                        }
                    },
                    {"$literal": True},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((if(mapContains(any(calls_merged.attributes_map_bool), {pb_0:String}),
                 any(calls_merged.attributes_map_bool)[{pb_0:String}],
                 (JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}) = 'true'))
             = {pb_2:Bool}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "env", "pb_1": '$."env"', "pb_2": True, "pb_3": "p"},
    )


def test_typed_map_dispatch_on_calls_merged_string() -> None:
    """``$convert(attributes.env, string)`` on calls_merged.

    Fast branch: ``any(attributes_map_str)[key]``.
    Fallback: ``toString(coalesce(nullIf(JSON_VALUE(...), 'null'), ''))``.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.env"},
                            "to": "string",
                        }
                    },
                    {"$literal": "prod"},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((if(mapContains(any(calls_merged.attributes_map_str), {pb_0:String}),
                 any(calls_merged.attributes_map_str)[{pb_0:String}],
                 toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "env", "pb_1": '$."env"', "pb_2": "prod", "pb_3": "p"},
    )


# ---------------------------------------------------------------------------
# calls_complete dispatch + nested attribute paths
# ---------------------------------------------------------------------------


def test_typed_map_dispatch_on_calls_complete() -> None:
    """calls_complete uses the unwrapped typed column (no any() aggregation).

    The mapContains gate still emits around each lookup so a not-yet-backfilled
    row in calls_complete (e.g. migrated from call_parts before 030) reads the
    attributes_dump fallback rather than the Map default.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.retries"},
                            "to": "int",
                        }
                    },
                    {"$literal": 3},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_complete.id AS id
        FROM calls_complete
        PREWHERE calls_complete.project_id = {pb_4:String}
        WHERE 1
          AND (((if(mapContains(calls_complete.attributes_map_int, {pb_0:String}),
                    calls_complete.attributes_map_int[{pb_0:String}],
                    toInt64OrNull(coalesce(nullIf(JSON_VALUE(calls_complete.attributes_dump, {pb_1:String}), 'null'), '')))
                 > {pb_2:Int64}))
               AND ((calls_complete.deleted_at = {pb_3:DateTime64(3)})))
        """,
        {
            "pb_0": "retries",
            "pb_1": '$."retries"',
            "pb_2": 3,
            "pb_3": SENTINEL_DATETIME,
            "pb_4": "p",
        },
    )


def test_nested_attribute_path_joins_with_dot() -> None:
    """``attributes.a.b.c`` uses ``a.b.c`` as the typed-map key.

    The extractor flattens nested dicts with dot-joined keys, so the Map
    read-side uses the same joiner to hit the stored key. The JSON_VALUE
    fallback keeps its own JSONPath (``$."a"."b"."c"``) for legacy rows.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.a.b.c"},
                            "to": "int",
                        }
                    },
                    {"$literal": 5},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((if(mapContains(any(calls_merged.attributes_map_int), {pb_0:String}),
                 any(calls_merged.attributes_map_int)[{pb_0:String}],
                 toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:Int64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "a.b.c", "pb_1": '$."a"."b"."c"', "pb_2": 5, "pb_3": "p"},
    )


# ---------------------------------------------------------------------------
# Fall-through (no typed cast → JSON_VALUE path only, no map read)
# ---------------------------------------------------------------------------


def test_fallback_no_convert_uses_json_value_only() -> None:
    """A plain ``$getField`` on attributes.* — no ``$convert`` — stays on the
    JSON_VALUE path with no map read. This preserves read-path compatibility
    for clients that never adopted typed dispatch, and the LIKE prefilter on
    attributes_dump is the existing optimization for equality-on-string.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {"$getField": "attributes.env"},
                    {"$literal": "prod"},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        WHERE ((calls_merged.attributes_dump LIKE {pb_2:String} OR calls_merged.attributes_dump IS NULL))
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_0:String}), 'null'), '') = {pb_1:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": '$."env"', "pb_1": "prod", "pb_2": '%"prod"%', "pb_3": "p"},
    )


def test_fallback_convert_exists_uses_json_value_only() -> None:
    """``$convert(..., "exists")`` has no typed Map analogue, so it stays on
    the JSON_VALUE existence-check path (``... IS NOT NULL``) and does not
    touch any ``attributes_map_*`` column.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.env"},
                            "to": "exists",
                        }
                    },
                    {"$literal": True},
                ]
            }
        )
    )

    assert_sql(
        cq,
        """
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_2:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            (((coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_0:String}), 'null'), '') IS NOT NULL) = {pb_1:Bool}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": '$."env"', "pb_1": True, "pb_2": "p"},
    )


# ---------------------------------------------------------------------------
# Extractor (ingest-side)
# ---------------------------------------------------------------------------


def test_extract_typed_attrs_dispatch_and_edge_cases() -> None:
    """One dense assertion block covering type dispatch, flattening, drops, and cap.

    - bool branch must precede int branch (Python bool is a subclass of int);
    - dicts flatten to dot-joined keys so read-side ``attributes.a.b`` matches;
    - None values are dropped (not written as empty strings);
    - non-finite floats (NaN/+inf/-inf) are dropped;
    - non-scalars (list/tuple/etc.) land in the string map as JSON;
    - each map independently caps at MAX_TYPED_ATTR_ENTRIES_PER_MAP.
    """
    cap = MAX_TYPED_ATTR_ENTRIES_PER_MAP
    attrs: dict = {
        "s": "hello",
        "i": 42,
        "f": 3.14,
        "b": True,
        "b2": False,
        "none": None,
        "nan": float("nan"),
        "pinf": float("inf"),
        "ninf": float("-inf"),
        "nested": {"a": 1, "b": {"c": "deep"}},
        "list": [1, 2, 3],
    }
    for i in range(cap + 5):
        attrs[f"str_{i:05d}"] = f"v{i}"

    s, i, f, b = extract_typed_attrs(attrs)

    assert b == {"b": True, "b2": False}
    assert i == {"i": 42, "nested.a": 1}
    assert f == {"f": 3.14}
    assert s["s"] == "hello"
    assert s["nested.b.c"] == "deep"
    assert s["list"] == "[1, 2, 3]"
    assert "none" not in s
    assert "none" not in i
    assert "none" not in f
    assert "none" not in b
    assert "nan" not in f
    assert "pinf" not in f
    assert "ninf" not in f
    assert len(s) == cap
    assert len(b) == 2
    assert len(i) == 2
    assert len(f) == 1


def test_extract_typed_attrs_non_dict_input() -> None:
    """Non-dict input returns four empty maps rather than raising."""
    assert extract_typed_attrs(None) == ({}, {}, {}, {})  # type: ignore[arg-type]
    assert extract_typed_attrs("not a dict") == ({}, {}, {}, {})  # type: ignore[arg-type]
