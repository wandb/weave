"""SQL shape assertions for every `make_*_query` in the insights query builder.

Each test builds a `ParamBuilder`, calls the builder, and compares the full
formatted SQL plus the exact param dict, matching the style of
`test_agent_query_builder.py`.

The expected column lists and measure block are spelled out literally rather
than composed from the builder's own constants, so changing what the builder
selects has to be a deliberate edit here too.
"""

import datetime
import uuid

import pytest

from tests.trace_server.query_builder.utils import assert_raw_sql
from weave.trace_server.insights.types import (
    InsightSignatureCursor,
    InsightSignaturesQueryReq,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.insights_query_builder import (
    PARAM_NAMESPACE,
    make_signature_groups_query,
    make_signature_rows_query,
)

PROJECT = "p1"
DAY_START = datetime.date(2026, 6, 1)
DAY_END = datetime.date(2026, 6, 30)
MID_DAY = datetime.date(2026, 6, 15)
CURSOR_ID = uuid.UUID("0197a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b")

SHARED_COLS = (
    "id, signature, hex(sipHash128(signature)) AS signature_hash, category, "
    "conversation_id, user_id, agent_name, turn_duration_ms, turn_cost_usd, "
    "trace_started_at, inserted_at"
)
INTENT_COLS = f"{SHARED_COLS}, trace_id, sentiment"
FAILURE_COLS = (
    f"{SHARED_COLS}, current_trace_id, affected_trace_ids, evidence_span_ids, "
    "failure_reason, severity"
)

BASE_WHERE = (
    "project_id = {insights_0:String} "
    "AND toDate(trace_started_at) >= {insights_1:Date} "
    "AND toDate(trace_started_at) <= {insights_2:Date}"
)
BASE_PARAMS = {
    "insights_0": PROJECT,
    "insights_1": DAY_START,
    "insights_2": DAY_END,
}

GROUP_MEASURES = """
    count() AS occurrences,
    uniq(conversation_id) AS conversations,
    uniq(user_id) AS users,
    topK(1)(category)[1] AS modal_category,
    avg(turn_cost_usd) AS avg_turn_cost_usd,
    quantile(0.5)(turn_duration_ms) AS p50_turn_duration_ms,
    topK(3)(config_sha) AS configs
"""


def assert_sql(
    expected_query: str, expected_params: dict, query: str, params: dict
) -> None:
    assert_raw_sql(query.strip(), expected_query.strip(), params, expected_params)


def rows_req(**overrides: object) -> InsightSignaturesQueryReq:
    fields: dict[str, object] = {
        "project_id": PROJECT,
        "signature_type": "intent",
        "day_start": DAY_START,
        "day_end": DAY_END,
    }
    fields.update(overrides)
    return InsightSignaturesQueryReq(**fields)


def unvalidated_rows_req(**overrides: object) -> InsightSignaturesQueryReq:
    """A request holding a value the `Literal` annotations would reject.

    The builders raise on unknown enum members rather than falling through, and
    that branch is only reachable if validation is bypassed.
    """
    fields: dict[str, object] = {
        "project_id": PROJECT,
        "signature_type": "intent",
        "day_start": DAY_START,
        "day_end": DAY_END,
    }
    fields.update(overrides)
    return InsightSignaturesQueryReq.model_construct(**fields)


def expected_rows_sql(
    *, columns: str, table: str, where: str, order_by: str, limit_slot: str
) -> str:
    """The fixed skeleton of a rows read. Every test supplies its own content."""
    return f"""
        SELECT {columns}
        FROM {table}
        WHERE {where}
        ORDER BY {order_by}
        LIMIT {limit_slot}
    """


def expected_groups_sql(
    *, group_exprs: str, table: str, where: str, group_keys: str, limit_slot: str
) -> str:
    return f"""
        SELECT {group_exprs}, {GROUP_MEASURES}
        FROM {table}
        WHERE {where}
        GROUP BY {group_keys}
        ORDER BY occurrences DESC
        LIMIT {limit_slot}
    """


def build_rows(req: InsightSignaturesQueryReq) -> tuple[str, dict]:
    pb = ParamBuilder(PARAM_NAMESPACE)
    return make_signature_rows_query(pb, req), pb.get_params()


def build_groups(req: InsightSignaturesQueryReq) -> tuple[str, dict]:
    pb = ParamBuilder(PARAM_NAMESPACE)
    return make_signature_groups_query(pb, req), pb.get_params()


# The signature type picks the table and the type-specific tail of the projection.
@pytest.mark.parametrize(
    ("overrides", "columns", "table"),
    [
        pytest.param({}, INTENT_COLS, "intent_signatures", id="intent"),
        pytest.param(
            {"signature_type": "failure"},
            FAILURE_COLS,
            "failure_signatures",
            id="failure",
        ),
        pytest.param(
            {"include_vector": True},
            f"{INTENT_COLS}, vector",
            "intent_signatures",
            id="vector_is_appended_last",
        ),
    ],
)
def test_signature_rows_projection(overrides: dict, columns: str, table: str) -> None:
    query, params = build_rows(rows_req(**overrides))
    expected = expected_rows_sql(
        columns=columns,
        table=table,
        where=BASE_WHERE,
        order_by="trace_started_at DESC, id",
        limit_slot="{insights_3:UInt32}",
    )
    assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


def test_key_order_without_a_cursor_is_the_first_page() -> None:
    query, params = build_rows(rows_req(order="key"))
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=BASE_WHERE,
        order_by="toDate(trace_started_at), id",
        limit_slot="{insights_3:UInt32}",
    )
    assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


def test_cursor_is_spelled_out_as_an_or_not_a_tuple_comparison() -> None:
    """A tuple comparison never reaches the primary key, so it must not appear."""
    query, params = build_rows(
        rows_req(order="key", cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID))
    )
    seek = (
        "(toDate(trace_started_at) > {insights_3:Date} "
        "OR (toDate(trace_started_at) = {insights_3:Date} "
        "AND id > {insights_4:UUID}))"
    )
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=f"{BASE_WHERE} AND {seek}",
        order_by="toDate(trace_started_at), id",
        limit_slot="{insights_5:UInt32}",
    )
    assert_sql(
        expected,
        {
            **BASE_PARAMS,
            "insights_3": MID_DAY,
            "insights_4": str(CURSOR_ID),
            "insights_5": 100,
        },
        query,
        params,
    )


def test_a_cursor_is_ignored_when_ordering_by_recency() -> None:
    """`recent` order has no stable seek, so the cursor must not leak in."""
    query, params = build_rows(
        rows_req(
            order="recent", cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID)
        )
    )
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=BASE_WHERE,
        order_by="trace_started_at DESC, id",
        limit_slot="{insights_3:UInt32}",
    )
    assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


def test_a_single_day_range_binds_one_slot_twice() -> None:
    """`ParamBuilder` dedupes on (type, value), so both bounds share a slot."""
    query, params = build_rows(rows_req(day_end=DAY_START))
    where = (
        "project_id = {insights_0:String} "
        "AND toDate(trace_started_at) >= {insights_1:Date} "
        "AND toDate(trace_started_at) <= {insights_1:Date}"
    )
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=where,
        order_by="trace_started_at DESC, id",
        limit_slot="{insights_2:UInt32}",
    )
    assert_sql(
        expected,
        {"insights_0": PROJECT, "insights_1": DAY_START, "insights_2": 100},
        query,
        params,
    )


def test_a_cursor_on_the_range_start_reuses_the_range_slot() -> None:
    query, params = build_rows(
        rows_req(
            order="key", cursor=InsightSignatureCursor(day=DAY_START, id=CURSOR_ID)
        )
    )
    seek = (
        "(toDate(trace_started_at) > {insights_1:Date} "
        "OR (toDate(trace_started_at) = {insights_1:Date} "
        "AND id > {insights_3:UUID}))"
    )
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=f"{BASE_WHERE} AND {seek}",
        order_by="toDate(trace_started_at), id",
        limit_slot="{insights_4:UInt32}",
    )
    assert_sql(
        expected,
        {**BASE_PARAMS, "insights_3": str(CURSOR_ID), "insights_4": 100},
        query,
        params,
    )


@pytest.mark.parametrize(
    ("overrides", "clause", "extra_params"),
    [
        pytest.param(
            {"trace_id": "t1"},
            "trace_id = {insights_3:String}",
            {"insights_3": "t1"},
            id="intent_trace_id_is_equality",
        ),
        pytest.param(
            {"trace_id": ""},
            "trace_id = {insights_3:String}",
            {"insights_3": ""},
            id="empty_trace_id_is_still_a_filter",
        ),
        pytest.param(
            {"conversation_id": "c1"},
            "conversation_id = {insights_3:String}",
            {"insights_3": "c1"},
            id="conversation_id",
        ),
        pytest.param(
            {"categories": ["action_request", "other"]},
            "category IN {insights_3:Array(String)}",
            {"insights_3": ["action_request", "other"]},
            id="categories",
        ),
        pytest.param(
            {"signature_hashes": ["abcd", "EF01"]},
            "hex(sipHash128(signature)) IN {insights_3:Array(String)}",
            {"insights_3": ["ABCD", "EF01"]},
            id="signature_hashes_are_uppercased_to_match_hex",
        ),
    ],
)
def test_single_filter(overrides: dict, clause: str, extra_params: dict) -> None:
    query, params = build_rows(rows_req(**overrides))
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=f"{BASE_WHERE} AND {clause}",
        order_by="trace_started_at DESC, id",
        limit_slot="{insights_4:UInt32}",
    )
    assert_sql(
        expected, {**BASE_PARAMS, **extra_params, "insights_4": 100}, query, params
    )


def test_failure_trace_id_is_array_membership() -> None:
    """A failure spans turns, so a turn drilldown is `has`, not equality."""
    query, params = build_rows(rows_req(signature_type="failure", trace_id="t1"))
    expected = expected_rows_sql(
        columns=FAILURE_COLS,
        table="failure_signatures",
        where=f"{BASE_WHERE} AND has(affected_trace_ids, {{insights_3:String}})",
        order_by="trace_started_at DESC, id",
        limit_slot="{insights_4:UInt32}",
    )
    assert_sql(
        expected,
        {**BASE_PARAMS, "insights_3": "t1", "insights_4": 100},
        query,
        params,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"categories": []}, id="empty_categories"),
        pytest.param({"signature_hashes": []}, id="empty_signature_hashes"),
    ],
)
def test_an_empty_list_adds_no_clause(overrides: dict) -> None:
    """An empty `IN ()` would match nothing, which is not what absent means."""
    query, params = build_rows(rows_req(**overrides))
    expected = expected_rows_sql(
        columns=INTENT_COLS,
        table="intent_signatures",
        where=BASE_WHERE,
        order_by="trace_started_at DESC, id",
        limit_slot="{insights_3:UInt32}",
    )
    assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


def test_every_filter_together_in_allocation_order() -> None:
    query, params = build_rows(
        rows_req(
            signature_type="failure",
            trace_id="t1",
            conversation_id="c1",
            categories=["other"],
            signature_hashes=["ab"],
            include_vector=True,
            order="key",
            cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID),
            limit=7,
        )
    )
    where = (
        f"{BASE_WHERE}"
        " AND has(affected_trace_ids, {insights_3:String})"
        " AND conversation_id = {insights_4:String}"
        " AND category IN {insights_5:Array(String)}"
        " AND hex(sipHash128(signature)) IN {insights_6:Array(String)}"
        " AND (toDate(trace_started_at) > {insights_7:Date}"
        " OR (toDate(trace_started_at) = {insights_7:Date}"
        " AND id > {insights_8:UUID}))"
    )
    expected = expected_rows_sql(
        columns=f"{FAILURE_COLS}, vector",
        table="failure_signatures",
        where=where,
        order_by="toDate(trace_started_at), id",
        limit_slot="{insights_9:UInt32}",
    )
    assert_sql(
        expected,
        {
            **BASE_PARAMS,
            "insights_3": "t1",
            "insights_4": "c1",
            "insights_5": ["other"],
            "insights_6": ["AB"],
            "insights_7": MID_DAY,
            "insights_8": str(CURSOR_ID),
            "insights_9": 7,
        },
        query,
        params,
    )


@pytest.mark.parametrize(
    ("signature_type", "group_by", "group_exprs", "group_keys", "table"),
    [
        pytest.param(
            "intent",
            ["signature"],
            "signature",
            "signature",
            "intent_signatures",
            id="signature_default",
        ),
        pytest.param(
            "intent",
            ["day"],
            "toDate(trace_started_at) AS day",
            "day",
            "intent_signatures",
            id="day_groups_on_its_alias",
        ),
        pytest.param(
            "intent",
            ["category", "agent_name", "day"],
            "category, agent_name, toDate(trace_started_at) AS day",
            "category, agent_name, day",
            "intent_signatures",
            id="several_fields_keep_request_order",
        ),
        pytest.param(
            "intent",
            ["sentiment"],
            "sentiment",
            "sentiment",
            "intent_signatures",
            id="sentiment_on_the_intent_type",
        ),
        pytest.param(
            "failure",
            ["severity"],
            "severity",
            "severity",
            "failure_signatures",
            id="severity_on_the_failure_type",
        ),
        pytest.param(
            "failure",
            ["agent_name"],
            "agent_name",
            "agent_name",
            "failure_signatures",
            id="a_shared_field_on_the_failure_type",
        ),
    ],
)
def test_group_by(
    signature_type: str,
    group_by: list[str],
    group_exprs: str,
    group_keys: str,
    table: str,
) -> None:
    query, params = build_groups(
        rows_req(signature_type=signature_type, mode="groups", group_by=group_by)
    )
    expected = expected_groups_sql(
        group_exprs=group_exprs,
        table=table,
        where=BASE_WHERE,
        group_keys=group_keys,
        limit_slot="{insights_3:UInt32}",
    )
    assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


def test_filters_apply_to_groups_the_same_way() -> None:
    query, params = build_groups(
        rows_req(mode="groups", conversation_id="c1", categories=["other"])
    )
    where = (
        f"{BASE_WHERE}"
        " AND conversation_id = {insights_3:String}"
        " AND category IN {insights_4:Array(String)}"
    )
    expected = expected_groups_sql(
        group_exprs="signature",
        table="intent_signatures",
        where=where,
        group_keys="signature",
        limit_slot="{insights_5:UInt32}",
    )
    assert_sql(
        expected,
        {
            **BASE_PARAMS,
            "insights_3": "c1",
            "insights_4": ["other"],
            "insights_5": 100,
        },
        query,
        params,
    )


def test_a_cursor_never_reaches_a_grouped_read() -> None:
    """Groups have no keyset order, so the cursor must be inert here."""
    query, params = build_groups(
        rows_req(
            mode="groups",
            order="key",
            cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID),
        )
    )
    expected = expected_groups_sql(
        group_exprs="signature",
        table="intent_signatures",
        where=BASE_WHERE,
        group_keys="signature",
        limit_slot="{insights_3:UInt32}",
    )
    assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


@pytest.mark.parametrize(
    ("signature_type", "field", "valid_on"),
    [
        pytest.param("failure", "sentiment", "intent", id="sentiment_on_failure"),
        pytest.param("intent", "severity", "failure", id="severity_on_intent"),
    ],
)
def test_a_type_only_group_field_is_rejected_on_the_other_type(
    signature_type: str, field: str, valid_on: str
) -> None:
    with pytest.raises(
        ValueError, match=f"only valid on the {valid_on} signature type"
    ):
        build_groups(
            rows_req(signature_type=signature_type, mode="groups", group_by=[field])
        )


def test_invalid_query_shapes_are_rejected() -> None:
    # A grouped query needs a key.
    with pytest.raises(ValueError, match="at least one group_by field"):
        build_groups(rows_req(mode="groups", group_by=[]))

    # Runtime callers can bypass the Literal annotations.
    with pytest.raises(ValueError, match="unknown insights group field"):
        build_groups(unvalidated_rows_req(mode="groups", group_by=["not_a_field"]))

    for build in (build_rows, build_groups):
        with pytest.raises(ValueError, match="unknown insights signature type"):
            build(unvalidated_rows_req(signature_type="sideways", mode="groups"))

    with pytest.raises(ValueError, match="unknown insights row order"):
        build_rows(unvalidated_rows_req(order="sideways"))
