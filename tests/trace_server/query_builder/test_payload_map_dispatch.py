"""Tests for the typed inputs/output Map fast-filter dispatch.

When a caller filters on ``inputs.<path>`` or ``output.<path>`` with an
explicit ``$convert`` cast (or a string-literal peer for the implicit-string
shape), the query builder emits a hybrid
``if(mapContains(map, key), map[key], JSON_VALUE fallback)`` expression: the
typed Map column wins on rows where migration 031 populated it at ingest,
and the old JSON_VALUE path takes over on legacy rows whose maps are still
empty. This file asserts the full SQL shape end-to-end on both read tables
plus the fall-through cases (no cast, ``exists`` cast, IS NULL peer).

Each test is intentionally un-parametrized and pins the complete query
shape — the SQL layer is load-bearing enough that a shared template or
fuzzy match would miss regressions at the punctuation level.
"""

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.clickhouse.utilities import (
    PAYLOAD_MAP_MAX_ENTRIES,
    PAYLOAD_MAP_STRING_MAX_LEN,
    extract_typed_inputs,
    extract_typed_output,
)
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ReadTable

# ---------------------------------------------------------------------------
# calls_merged dispatch — inputs.* (one test per supported cast)
# ---------------------------------------------------------------------------


def test_typed_inputs_map_dispatch_on_calls_merged_int() -> None:
    """``$convert(inputs.retries, int)`` on calls_merged.

    Fast branch: ``any(inputs_map_int)[key]``.
    Fallback: ``toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(inputs_dump), ...), 'null'), ''))``.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.retries"},
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
        SELECT calls_merged.id AS id
        FROM calls_merged
        PREWHERE calls_merged.project_id = {pb_3:String}
        GROUP BY (calls_merged.project_id, calls_merged.id)
        HAVING (
            ((if(mapContains(any(calls_merged.inputs_map_int), {pb_0:String}),
                 any(calls_merged.inputs_map_int)[{pb_0:String}],
                 toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:Int64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "retries", "pb_1": '$."retries"', "pb_2": 3, "pb_3": "p"},
    )


def test_typed_inputs_map_dispatch_on_calls_merged_double() -> None:
    """``$convert(inputs.temperature, double)`` on calls_merged."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.temperature"},
                            "to": "double",
                        }
                    },
                    {"$literal": 0.7},
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
            ((if(mapContains(any(calls_merged.inputs_map_float), {pb_0:String}),
                 any(calls_merged.inputs_map_float)[{pb_0:String}],
                 toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:Float64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "temperature", "pb_1": '$."temperature"', "pb_2": 0.7, "pb_3": "p"},
    )


def test_typed_inputs_map_dispatch_on_calls_merged_bool() -> None:
    """``$convert(inputs.stream, bool)`` on calls_merged.

    Fallback compares ``JSON_VALUE`` to ``'true'`` directly because
    ``toUInt8OrNull('true')`` returns NULL and would silently drop legacy rows.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.stream"},
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
            ((if(mapContains(any(calls_merged.inputs_map_bool), {pb_0:String}),
                 any(calls_merged.inputs_map_bool)[{pb_0:String}],
                 (JSON_VALUE(any(calls_merged.inputs_dump), {pb_1:String}) = 'true'))
             = {pb_2:Bool}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "stream", "pb_1": '$."stream"', "pb_2": True, "pb_3": "p"},
    )


def test_typed_inputs_map_dispatch_on_calls_merged_string() -> None:
    """``$convert(inputs.model, string)`` on calls_merged."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.model"},
                            "to": "string",
                        }
                    },
                    {"$literal": "gpt-4"},
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
            ((if(mapContains(any(calls_merged.inputs_map_str), {pb_0:String}),
                 any(calls_merged.inputs_map_str)[{pb_0:String}],
                 toString(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_1:String}), 'null'), '')))
             = {pb_2:String}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "model", "pb_1": '$."model"', "pb_2": "gpt-4", "pb_3": "p"},
    )


def test_typed_inputs_map_dispatch_with_numeric_path_segment() -> None:
    """``$convert(inputs.in_val.list.0, int)`` — list-index path.

    Numeric segments must encode as ``[N]`` (array indexing), not
    ``."N"`` (object-key lookup). The fast branch never matches (lists
    are skipped at ingest, so ``mapContains`` is false) but the
    JSON_VALUE fallback must use the right shape so list-element reads
    keep working.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.in_val.list.0"},
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
            ((if(mapContains(any(calls_merged.inputs_map_int), {pb_0:String}),
                 any(calls_merged.inputs_map_int)[{pb_0:String}],
                 toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_1:String}), 'null'), '')))
             > {pb_2:Int64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": "in_val.list.0",
            "pb_1": '$."in_val"."list"[0]',
            "pb_2": 5,
            "pb_3": "p",
        },
    )


# ---------------------------------------------------------------------------
# calls_merged dispatch — output.* (parallel to inputs.*, narrower coverage)
# ---------------------------------------------------------------------------


def test_typed_output_map_dispatch_on_calls_merged_int() -> None:
    """``$convert(output.usage.total_tokens, int)`` on calls_merged."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "output.usage.total_tokens"},
                            "to": "int",
                        }
                    },
                    {"$literal": 1000},
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
            ((if(mapContains(any(calls_merged.output_map_int), {pb_0:String}),
                 any(calls_merged.output_map_int)[{pb_0:String}],
                 toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.output_dump), {pb_1:String}), 'null'), '')))
             > {pb_2:Int64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {
            "pb_0": "usage.total_tokens",
            "pb_1": '$."usage"."total_tokens"',
            "pb_2": 1000,
            "pb_3": "p",
        },
    )


# ---------------------------------------------------------------------------
# calls_complete dispatch (no any() wrapper, mapContains gate still emitted)
# ---------------------------------------------------------------------------


def test_typed_inputs_map_dispatch_on_calls_complete() -> None:
    """``$convert(inputs.retries, int)`` on calls_complete.

    Direct column reads — no ``any()`` wrapping. The mapContains gate still
    emits so a row migrated from call_parts before 031 falls back to the
    inputs_dump JSON_VALUE branch instead of reading the Map default.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.retries"},
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
          AND (((if(mapContains(calls_complete.inputs_map_int, {pb_0:String}),
                    calls_complete.inputs_map_int[{pb_0:String}],
                    toInt64OrNull(coalesce(nullIf(JSON_VALUE(calls_complete.inputs_dump, {pb_1:String}), 'null'), '')))
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


def test_typed_output_map_dispatch_on_calls_complete() -> None:
    """``$convert(output.usage.total_tokens, int)`` on calls_complete."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {
                        "$convert": {
                            "input": {"$getField": "output.usage.total_tokens"},
                            "to": "int",
                        }
                    },
                    {"$literal": 1000},
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
          AND (((if(mapContains(calls_complete.output_map_int, {pb_0:String}),
                    calls_complete.output_map_int[{pb_0:String}],
                    toInt64OrNull(coalesce(nullIf(JSON_VALUE(calls_complete.output_dump, {pb_1:String}), 'null'), '')))
                 > {pb_2:Int64}))
               AND ((calls_complete.deleted_at = {pb_3:DateTime64(3)})))
        """,
        {
            "pb_0": "usage.total_tokens",
            "pb_1": '$."usage"."total_tokens"',
            "pb_2": 1000,
            "pb_3": SENTINEL_DATETIME,
            "pb_4": "p",
        },
    )


# ---------------------------------------------------------------------------
# Fall-through cases: dispatch must NOT fire so the JSON_VALUE path stays.
# ---------------------------------------------------------------------------


def test_no_convert_no_string_literal_falls_through() -> None:
    """``inputs.x > 3`` (no $convert, peer is an int literal) — implicit-
    string fast path requires a string peer, and there's no $convert, so
    the dispatch returns None and the plain JSON_VALUE shape is emitted.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "inputs.retries"},
                    {"$literal": 3},
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
            ((coalesce(nullIf(JSON_VALUE(any(calls_merged.inputs_dump), {pb_0:String}), 'null'), '') > {pb_1:Int64}))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": '$."retries"', "pb_1": 3, "pb_2": "p"},
    )


def test_convert_to_exists_falls_through() -> None:
    """``$convert(inputs.x, exists)`` has no typed Map — falls through."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "inputs.retries"},
                            "to": "exists",
                        }
                    },
                    {"$literal": True},
                ]
            }
        )
    )

    # We don't need to pin the exact fallback shape (already covered by
    # other tests); we just need to confirm no inputs_map_* column appears
    # in the emitted SQL.
    pb = ParamBuilder("pb")
    sql = cq.as_sql(pb)
    assert "inputs_map_int" not in sql
    assert "inputs_map_str" not in sql
    assert "inputs_map_float" not in sql
    assert "inputs_map_bool" not in sql


def test_non_payload_field_falls_through() -> None:
    """``$convert(attributes.foo, int)`` is not an inputs/output path so the
    dispatch returns None and the standard JSON_VALUE shape stands.
    """
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.EqOperation.model_validate(
            {
                "$eq": [
                    {
                        "$convert": {
                            "input": {"$getField": "attributes.foo"},
                            "to": "int",
                        }
                    },
                    {"$literal": 1},
                ]
            }
        )
    )

    pb = ParamBuilder("pb")
    sql = cq.as_sql(pb)
    assert "inputs_map" not in sql
    assert "output_map" not in sql


# ---------------------------------------------------------------------------
# extract_typed_inputs / extract_typed_output — ingest-side correctness
# ---------------------------------------------------------------------------


def test_extract_typed_inputs_routes_by_python_type() -> None:
    inputs = {
        "model": "gpt-4",
        "temperature": 0.7,
        "stream": True,
        "max_tokens": 256,
        "messages": [{"role": "user"}],  # list — entire leaf skipped
        "config": {"top_p": 0.9, "verbose": False},  # nested dict — descended
    }
    maps = extract_typed_inputs(inputs)
    assert maps["inputs_map_str"] == {"model": "gpt-4"}
    assert maps["inputs_map_int"] == {"max_tokens": 256}
    assert maps["inputs_map_float"] == {"temperature": 0.7, "config.top_p": 0.9}
    assert maps["inputs_map_bool"] == {"stream": True, "config.verbose": False}


def test_extract_typed_output_handles_non_dict() -> None:
    """Non-dict outputs (string, int, list) skip the typed maps entirely;
    JSON_VALUE fallback still answers filters against them.
    """
    assert extract_typed_output("just a string") == {
        "output_map_str": {},
        "output_map_int": {},
        "output_map_float": {},
        "output_map_bool": {},
    }
    assert extract_typed_output(42) == {
        "output_map_str": {},
        "output_map_int": {},
        "output_map_float": {},
        "output_map_bool": {},
    }


def test_extract_typed_inputs_skips_long_strings() -> None:
    """Strings longer than the cap don't make sense as exact-match filter
    targets and dominate column size, so they're dropped from the map.
    Filters fall back to JSON_VALUE on ``inputs_dump`` for those keys.
    """
    big = "x" * (PAYLOAD_MAP_STRING_MAX_LEN + 1)
    small = "y" * PAYLOAD_MAP_STRING_MAX_LEN
    maps = extract_typed_inputs({"big_field": big, "small_field": small})
    assert maps["inputs_map_str"] == {"small_field": small}


def test_extract_typed_inputs_caps_total_entries() -> None:
    """Past the per-row cap, leaves are dropped (still answerable via
    JSON_VALUE fallback). Cap applies to the sum across all four maps.
    """
    inputs = {f"k_{i}": i for i in range(PAYLOAD_MAP_MAX_ENTRIES + 50)}
    maps = extract_typed_inputs(inputs)
    assert len(maps["inputs_map_int"]) == PAYLOAD_MAP_MAX_ENTRIES


def test_extract_typed_inputs_drops_non_finite_floats() -> None:
    maps = extract_typed_inputs(
        {
            "ok": 1.5,
            "nan": float("nan"),
            "posinf": float("inf"),
            "neginf": float("-inf"),
        }
    )
    assert maps["inputs_map_float"] == {"ok": 1.5}


def test_extract_typed_inputs_bool_before_int() -> None:
    """Python ``bool`` subclasses ``int``, so an int-first dispatch would
    misroute True/False into inputs_map_int. Pin the dispatch order.
    """
    maps = extract_typed_inputs({"flag": True, "count": 1})
    assert maps["inputs_map_bool"] == {"flag": True}
    assert maps["inputs_map_int"] == {"count": 1}
