"""Tests for the typed attributes-map fast-filter dispatch.

When a caller filters on ``attributes.<path>`` with an explicit ``$convert``
cast or compares it to a scalar literal with an inferable type, the query
builder emits a hybrid
``if(mapContains(map, key), map[key], clickhouse_cast(JSON_VALUE(...)))``
expression: the typed Map column wins on rows where migration 031 populated
it at ingest, and the old JSON_VALUE path takes over on legacy rows whose
maps are still empty. This file asserts the full SQL shape end-to-end on
both read tables plus the fall-through cases (``exists`` cast, ambiguous
literal types).

The SQL layer is load-bearing enough that these tests pin complete query
shapes; where one test groups related subcases, each subcase still asserts the
full emitted SQL rather than a fuzzy fragment.
"""

from tests.trace_server.query_builder.utils import assert_sql
from weave.trace_server.calls_query_builder.calls_query_builder import CallsQuery
from weave.trace_server.ch_sentinel_values import SENTINEL_DATETIME
from weave.trace_server.clickhouse.utilities import extract_typed_attrs
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
    row in calls_complete (e.g. migrated from call_parts before 031) reads the
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
# Literal-inferred dispatch (no $convert required)
# ---------------------------------------------------------------------------


def test_literal_inference_eq_uses_typed_map_on_calls_merged() -> None:
    """Unconverted equality filters infer typed maps from scalar literals.

    This is the PR comment's proposed shape: callers can send
    ``attributes.<key> = <typed literal>`` and omit ``$convert`` as long as
    the literal is already the type they mean to compare against. The four
    subcases intentionally live in one test so the SQL shape is easy to
    compare across map types.
    """
    cases = [
        # string
        (
            "env",
            "prod",
            "attributes_map_str",
            "String",
            "coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')",
            '%"prod"%',
        ),
        # int
        (
            "retries",
            3,
            "attributes_map_int",
            "Int64",
            "toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), ''))",
            "%3%",
        ),
        # double
        (
            "score",
            0.9,
            "attributes_map_float",
            "Float64",
            "toFloat64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), ''))",
            "%0.9%",
        ),
        # bool
        (
            "enabled",
            True,
            "attributes_map_bool",
            "Bool",
            "(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}) = 'true')",
            "%true%",
        ),
    ]

    for attr_key, literal, column, literal_type, fallback_sql, like_pattern in cases:
        cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
        cq.add_field("id")
        cq.add_condition(
            tsi_query.EqOperation.model_validate(
                {
                    "$eq": [
                        {"$getField": f"attributes.{attr_key}"},
                        {"$literal": literal},
                    ]
                }
            )
        )

        assert_sql(
            cq,
            f"""
            SELECT calls_merged.id AS id
            FROM calls_merged
            PREWHERE calls_merged.project_id = {{pb_4:String}}
            WHERE ((calls_merged.attributes_dump LIKE {{pb_3:String}} OR calls_merged.attributes_dump IS NULL))
            GROUP BY (calls_merged.project_id, calls_merged.id)
            HAVING (
                ((if(mapContains(any(calls_merged.{column}), {{pb_0:String}}),
                     any(calls_merged.{column})[{{pb_0:String}}],
                     {fallback_sql})
                 = {{pb_2:{literal_type}}}))
                AND ((any(calls_merged.deleted_at) IS NULL))
                AND ((NOT ((any(calls_merged.started_at) IS NULL))))
            )
            """,
            {
                "pb_0": attr_key,
                "pb_1": f'$."{attr_key}"',
                "pb_2": literal,
                "pb_3": like_pattern,
                "pb_4": "p",
            },
        )


def test_literal_inference_gt_uses_typed_map_on_calls_complete() -> None:
    """Range comparisons infer numeric typed maps on calls_complete too."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_COMPLETE)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.GtOperation.model_validate(
            {
                "$gt": [
                    {"$getField": "attributes.retries"},
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


def test_literal_inference_when_field_is_rhs_preserves_operator_direction() -> None:
    """``3 < attributes.retries`` keeps the field on the RHS of the operator."""
    cq = CallsQuery(project_id="p", read_table=ReadTable.CALLS_MERGED)
    cq.add_field("id")
    cq.add_condition(
        tsi_query.LtOperation.model_validate(
            {
                "$lt": [
                    {"$literal": 3},
                    {"$getField": "attributes.retries"},
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
            (({pb_2:Int64} < if(mapContains(any(calls_merged.attributes_map_int), {pb_0:String}),
                 any(calls_merged.attributes_map_int)[{pb_0:String}],
                 toInt64OrNull(coalesce(nullIf(JSON_VALUE(any(calls_merged.attributes_dump), {pb_1:String}), 'null'), '')))))
            AND ((any(calls_merged.deleted_at) IS NULL))
            AND ((NOT ((any(calls_merged.started_at) IS NULL))))
        )
        """,
        {"pb_0": "retries", "pb_1": '$."retries"', "pb_2": 3, "pb_3": "p"},
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
    """One dense assertion block covering type dispatch, flattening, and drops.

    - bool branch must precede int branch (Python bool is a subclass of int);
    - dicts flatten to dot-joined keys so read-side ``attributes.a.b`` matches;
    - None values are dropped (not written as empty strings);
    - non-finite floats (NaN/+inf/-inf) are dropped;
    - non-scalars (list/tuple/etc.) land in the string map as JSON;
    - no entry cap: oversized rows are handled downstream by
      ``_strip_large_values``, not by truncating the extractor output.
    """
    big_batch = 250  # well above the removed 100-entry cap.
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
    for i in range(big_batch):
        attrs[f"str_{i:05d}"] = f"v{i}"

    maps = extract_typed_attrs(attrs)
    s = maps["attributes_map_str"]
    i = maps["attributes_map_int"]
    f = maps["attributes_map_float"]
    b = maps["attributes_map_bool"]

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
    # All big_batch str_NNNNN entries survive + s/nested.b.c/list = big_batch + 3.
    assert len(s) == big_batch + 3
    assert len(b) == 2
    assert len(i) == 2
    assert len(f) == 1


def test_extract_typed_attrs_non_dict_input() -> None:
    """Non-dict input returns empty maps rather than raising."""
    empty = {
        "attributes_map_str": {},
        "attributes_map_int": {},
        "attributes_map_float": {},
        "attributes_map_bool": {},
    }
    assert extract_typed_attrs(None) == empty  # type: ignore[arg-type]
    assert extract_typed_attrs("not a dict") == empty  # type: ignore[arg-type]


def test_extract_typed_attrs_dot_key_collision_is_documented() -> None:
    """``{"a": {"b": 1}}`` and ``{"a.b": 2}`` both flatten to key ``"a.b"``.

    The second write wins in the typed Map because Python dicts are
    insertion-ordered and ``extract_typed_attrs`` iterates once per leaf.
    The JSON_VALUE fallback can still distinguish them (``$."a"."b"`` vs
    ``$."a.b"``) — so a row with a literal-dot key would read different
    values from the fast and fallback branches. We accept this divergence
    because nested dicts are the common shape and literal-dot keys
    already break the JSONPath-based filter convention.

    This test pins the current behavior so it doesn't drift silently.
    """
    int_map = extract_typed_attrs({"a": {"b": 1}, "a.b": 2})["attributes_map_int"]
    assert int_map == {"a.b": 2}, (
        "Literal-dot key must overwrite the nested flattening (insertion order)."
    )

    int_map_reverse = extract_typed_attrs({"a.b": 2, "a": {"b": 1}})[
        "attributes_map_int"
    ]
    assert int_map_reverse == {"a.b": 1}, (
        "Nested flattening must overwrite the literal-dot key when inserted later."
    )
