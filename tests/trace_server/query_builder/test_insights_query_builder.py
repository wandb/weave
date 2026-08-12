"""SQL shape assertions for every `make_*_query` in the insights query builder.

Each test builds a `ParamBuilder`, calls the builder, and compares the full
formatted SQL plus the exact param dict, matching the style of
`test_agent_query_builder.py`.

The expected column lists and measure block are spelled out literally rather
than composed from the builder's own constants, so changing what the builder
selects has to be a deliberate edit here too.
"""

import datetime

import pytest
import sqlparse

from weave.trace_server.insights.types import (
    InsightContextQueryReq,
    InsightContextSignature,
    InsightSignatureCursor,
    InsightSignatureRow,
    InsightSignaturesQueryReq,
)
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.insights_query_builder import (
    CONTEXT_COLUMNS,
    FAILURE_ROW_COLUMNS,
    GROUP_EXPRESSIONS,
    INTENT_ROW_COLUMNS,
    PARAM_NAMESPACE,
    SHARED_ROW_COLUMNS,
    make_context_query,
    make_signature_groups_query,
    make_signature_rows_query,
)

PROJECT = "p1"
DAY_START = datetime.date(2026, 6, 1)
DAY_END = datetime.date(2026, 6, 30)
MID_DAY = datetime.date(2026, 6, 15)
CURSOR_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"

SHARED_COLS = (
    "id, signature, signature_display, "
    "hex(sipHash128(signature)) AS signature_hash, category, "
    "conversation_id, user_id, agent_name, duration_ms, cost_usd, "
    "source_started_at, inserted_at"
)
INTENT_COLS = f"{SHARED_COLS}, turn_trace_id, language, sentiment, sentiment_confidence"
FAILURE_COLS = (
    f"{SHARED_COLS}, onset_turn_trace_id, turn_trace_ids, evidence_span_ids, "
    "failure_reason, severity"
)

BASE_WHERE = (
    "project_id = {insights_0:String} "
    "AND toDate(source_started_at) >= {insights_1:Date} "
    "AND toDate(source_started_at) <= {insights_2:Date}"
)
BASE_PARAMS = {
    "insights_0": PROJECT,
    "insights_1": DAY_START,
    "insights_2": DAY_END,
}

GROUP_MEASURES = """
    uniqExact(id) AS occurrences,
    uniq(conversation_id) AS conversations,
    uniq(user_id) AS users,
    topK(1)(category)[1] AS modal_category,
    avg(cost_usd) AS avg_cost_usd,
    quantile(0.5)(duration_ms) AS p50_duration_ms,
    topK(3)(config_sha) AS configs
"""

CONTEXT_PARAMS = {
    "insights_0": PROJECT,
    "insights_1": "c1",
    "insights_2": DAY_START,
    "insights_3": DAY_END,
    "insights_4": ["t1", "t2"],
}


def assert_sql(
    expected_query: str, expected_params: dict, query: str, params: dict
) -> None:
    expected_formatted = sqlparse.format(expected_query, reindent=True).strip()
    found_formatted = sqlparse.format(query, reindent=True).strip()

    assert expected_formatted == found_formatted, (
        f"\nExpected:\n{expected_formatted}\n\nGot:\n{found_formatted}"
    )
    assert expected_params == params, (
        f"\nExpected params: {expected_params}\n\nGot params: {params}"
    )


def rows_req(**overrides: object) -> InsightSignaturesQueryReq:
    fields: dict[str, object] = {
        "project_id": PROJECT,
        "lens": "intent",
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
        "lens": "intent",
        "day_start": DAY_START,
        "day_end": DAY_END,
    }
    fields.update(overrides)
    return InsightSignaturesQueryReq.model_construct(**fields)


def context_req(**overrides: object) -> InsightContextQueryReq:
    fields: dict[str, object] = {
        "project_id": PROJECT,
        "conversation_id": "c1",
        "turn_trace_ids": ["t1", "t2"],
        "day_start": DAY_START,
        "day_end": DAY_END,
    }
    fields.update(overrides)
    return InsightContextQueryReq(**fields)


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


def expected_context_sql(
    *,
    project_slot: str,
    conversation_slot: str,
    turns_slot: str,
    day_start_slot: str = "{insights_2:Date}",
    day_end_slot: str = "{insights_3:Date}",
) -> str:
    """The union of both signature tables, unnested onto the requested turns."""
    scope = (
        f"project_id = {project_slot}\n"
        f"      AND conversation_id = {conversation_slot}\n"
        f"      AND toDate(source_started_at) >= {day_start_slot}\n"
        f"      AND toDate(source_started_at) <= {day_end_slot}"
    )
    return f"""
        SELECT lens, turn_trace_id, signature, signature_display, category,
               config_sha, source_started_at, id, inserted_at
        FROM
        (
            SELECT
                'intent' AS lens,
                turn_trace_id,
                signature,
                signature_display,
                category,
                config_sha,
                source_started_at,
                id,
                inserted_at
            FROM intent_signatures
            WHERE {scope}
              AND turn_trace_id IN {turns_slot}
            UNION ALL
            SELECT
                'failure' AS lens,
                arrayJoin(arrayFilter(t -> has({turns_slot}, t), turn_trace_ids)) AS turn_trace_id,
                signature,
                signature_display,
                category,
                config_sha,
                source_started_at,
                id,
                inserted_at
            FROM failure_signatures
            WHERE {scope}
              AND hasAny(turn_trace_ids, {turns_slot})
        )
        ORDER BY source_started_at ASC, lens ASC, id ASC
    """


def build_rows(req: InsightSignaturesQueryReq) -> tuple[str, dict]:
    pb = ParamBuilder(PARAM_NAMESPACE)
    return make_signature_rows_query(pb, req), pb.get_params()


def build_groups(req: InsightSignaturesQueryReq) -> tuple[str, dict]:
    pb = ParamBuilder(PARAM_NAMESPACE)
    return make_signature_groups_query(pb, req), pb.get_params()


def build_context(req: InsightContextQueryReq) -> tuple[str, dict]:
    pb = ParamBuilder(PARAM_NAMESPACE)
    return make_context_query(pb, req), pb.get_params()


# ============================================================================
# make_context_query
# ============================================================================


class TestMakeContextQuery:
    """One read over both signature tables: there is no per-turn table to use."""

    def test_both_lenses_for_the_requested_turns(self) -> None:
        query, params = build_context(context_req())
        expected = expected_context_sql(
            project_slot="{insights_0:String}",
            conversation_slot="{insights_1:String}",
            turns_slot="{insights_4:Array(String)}",
        )
        assert_sql(expected, CONTEXT_PARAMS, query, params)

    def test_the_turn_list_binds_one_slot_for_all_three_uses(self) -> None:
        """`ParamBuilder` dedupes, so the array is sent once and read three times."""
        query, params = build_context(context_req())
        assert query.count("{insights_4:Array(String)}") == 3
        assert list(params) == list(CONTEXT_PARAMS)

    def test_the_unnest_filters_to_the_requested_turns(self) -> None:
        """`hasAny` prunes on the bloom index; `arrayFilter` stops a failure
        spanning ten turns from returning the nine nobody asked for.
        """
        query, _ = build_context(context_req())
        assert (
            "arrayJoin(arrayFilter(t -> has({insights_4:Array(String)}, t), "
            "turn_trace_ids)) AS turn_trace_id" in query
        )
        assert "hasAny(turn_trace_ids, {insights_4:Array(String)})" in query

    def test_the_intent_lens_matches_its_single_turn_column(self) -> None:
        """An intent belongs to one turn, so its filter is `IN`, not `hasAny`."""
        query, _ = build_context(context_req())
        assert "AND turn_trace_id IN {insights_4:Array(String)}" in query

    def test_a_conversation_named_like_the_project_reuses_one_slot(self) -> None:
        query, params = build_context(context_req(conversation_id=PROJECT))
        expected = expected_context_sql(
            project_slot="{insights_0:String}",
            conversation_slot="{insights_0:String}",
            turns_slot="{insights_3:Array(String)}",
            day_start_slot="{insights_1:Date}",
            day_end_slot="{insights_2:Date}",
        )
        assert_sql(
            expected,
            {
                "insights_0": PROJECT,
                "insights_1": DAY_START,
                "insights_2": DAY_END,
                "insights_3": ["t1", "t2"],
            },
            query,
            params,
        )

    def test_a_single_day_range_binds_one_slot_twice(self) -> None:
        query, params = build_context(context_req(day_end=DAY_START))
        assert query.count("{insights_2:Date}") == 4
        assert params == {
            "insights_0": PROJECT,
            "insights_1": "c1",
            "insights_2": DAY_START,
            "insights_3": ["t1", "t2"],
        }


# ============================================================================
# make_signature_rows_query
# ============================================================================


class TestSignatureRowsLens:
    """The lens picks the table and the lens-specific tail of the projection."""

    def test_intent(self) -> None:
        query, params = build_rows(rows_req())
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=BASE_WHERE,
            order_by="source_started_at DESC, id",
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)

    def test_failure(self) -> None:
        query, params = build_rows(rows_req(lens="failure"))
        expected = expected_rows_sql(
            columns=FAILURE_COLS,
            table="failure_signatures",
            where=BASE_WHERE,
            order_by="source_started_at DESC, id",
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)

    def test_include_vector_appends_the_payload_column_last(self) -> None:
        query, params = build_rows(rows_req(include_vector=True))
        expected = expected_rows_sql(
            columns=f"{INTENT_COLS}, vector",
            table="intent_signatures",
            where=BASE_WHERE,
            order_by="source_started_at DESC, id",
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


class TestSignatureRowsOrdering:
    def test_key_order_without_a_cursor_is_the_first_page(self) -> None:
        query, params = build_rows(rows_req(order="key"))
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=BASE_WHERE,
            order_by="toDate(source_started_at), id",
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)

    def test_cursor_is_spelled_out_as_an_or_not_a_tuple_comparison(self) -> None:
        """A tuple comparison never reaches the primary key, so it must not appear."""
        query, params = build_rows(
            rows_req(
                order="key", cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID)
            )
        )
        seek = (
            "(toDate(source_started_at) > {insights_3:Date} "
            "OR (toDate(source_started_at) = {insights_3:Date} "
            "AND id > {insights_4:UUID}))"
        )
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=f"{BASE_WHERE} AND {seek}",
            order_by="toDate(source_started_at), id",
            limit_slot="{insights_5:UInt32}",
        )
        assert_sql(
            expected,
            {
                **BASE_PARAMS,
                "insights_3": MID_DAY,
                "insights_4": CURSOR_ID,
                "insights_5": 100,
            },
            query,
            params,
        )
        assert "), id) >" not in query

    def test_the_cursor_id_is_bound_as_a_uuid_not_a_string(self) -> None:
        """`id` is a UUID column: a String slot would not compare against it."""
        query, _ = build_rows(
            rows_req(
                order="key", cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID)
            )
        )
        assert "AND id > {insights_4:UUID}" in query

    def test_a_cursor_is_ignored_when_ordering_by_recency(self) -> None:
        """`recent` order has no stable seek, so the cursor must not leak in."""
        query, params = build_rows(
            rows_req(
                order="recent",
                cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID),
            )
        )
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=BASE_WHERE,
            order_by="source_started_at DESC, id",
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)


class TestSignatureRowsParamReuse:
    """`ParamBuilder` dedupes on (type, value); these pin where that shows up."""

    def test_a_single_day_range_binds_one_slot_twice(self) -> None:
        query, params = build_rows(rows_req(day_end=DAY_START))
        where = (
            "project_id = {insights_0:String} "
            "AND toDate(source_started_at) >= {insights_1:Date} "
            "AND toDate(source_started_at) <= {insights_1:Date}"
        )
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=where,
            order_by="source_started_at DESC, id",
            limit_slot="{insights_2:UInt32}",
        )
        assert_sql(
            expected,
            {"insights_0": PROJECT, "insights_1": DAY_START, "insights_2": 100},
            query,
            params,
        )

    def test_a_cursor_on_the_range_start_reuses_the_range_slot(self) -> None:
        query, params = build_rows(
            rows_req(
                order="key", cursor=InsightSignatureCursor(day=DAY_START, id=CURSOR_ID)
            )
        )
        seek = (
            "(toDate(source_started_at) > {insights_1:Date} "
            "OR (toDate(source_started_at) = {insights_1:Date} "
            "AND id > {insights_3:UUID}))"
        )
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=f"{BASE_WHERE} AND {seek}",
            order_by="toDate(source_started_at), id",
            limit_slot="{insights_4:UInt32}",
        )
        assert_sql(
            expected,
            {**BASE_PARAMS, "insights_3": CURSOR_ID, "insights_4": 100},
            query,
            params,
        )


class TestSignatureRowsFilters:
    @pytest.mark.parametrize(
        ("overrides", "clause", "extra_params"),
        [
            pytest.param(
                {"turn_trace_id": "t1"},
                "turn_trace_id = {insights_3:String}",
                {"insights_3": "t1"},
                id="intent_turn_trace_id_is_equality",
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
    def test_single_filter(
        self, overrides: dict, clause: str, extra_params: dict
    ) -> None:
        query, params = build_rows(rows_req(**overrides))
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=f"{BASE_WHERE} AND {clause}",
            order_by="source_started_at DESC, id",
            limit_slot="{insights_4:UInt32}",
        )
        assert_sql(
            expected, {**BASE_PARAMS, **extra_params, "insights_4": 100}, query, params
        )

    def test_failure_turn_trace_id_is_array_membership(self) -> None:
        """A failure spans turns, so a turn drilldown is `has`, not equality."""
        query, params = build_rows(rows_req(lens="failure", turn_trace_id="t1"))
        expected = expected_rows_sql(
            columns=FAILURE_COLS,
            table="failure_signatures",
            where=f"{BASE_WHERE} AND has(turn_trace_ids, {{insights_3:String}})",
            order_by="source_started_at DESC, id",
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
    def test_an_empty_list_adds_no_clause(self, overrides: dict) -> None:
        """An empty `IN ()` would match nothing, which is not what absent means."""
        query, params = build_rows(rows_req(**overrides))
        expected = expected_rows_sql(
            columns=INTENT_COLS,
            table="intent_signatures",
            where=BASE_WHERE,
            order_by="source_started_at DESC, id",
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)

    def test_an_empty_string_filter_is_still_a_predicate(self) -> None:
        """`turn_trace_id=""` is not None, so it filters rather than being dropped."""
        query, params = build_rows(rows_req(turn_trace_id=""))
        assert "turn_trace_id = {insights_3:String}" in query
        assert params["insights_3"] == ""

    def test_every_filter_together_in_allocation_order(self) -> None:
        query, params = build_rows(
            rows_req(
                lens="failure",
                turn_trace_id="t1",
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
            " AND has(turn_trace_ids, {insights_3:String})"
            " AND conversation_id = {insights_4:String}"
            " AND category IN {insights_5:Array(String)}"
            " AND hex(sipHash128(signature)) IN {insights_6:Array(String)}"
            " AND (toDate(source_started_at) > {insights_7:Date}"
            " OR (toDate(source_started_at) = {insights_7:Date}"
            " AND id > {insights_8:UUID}))"
        )
        expected = expected_rows_sql(
            columns=f"{FAILURE_COLS}, vector",
            table="failure_signatures",
            where=where,
            order_by="toDate(source_started_at), id",
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
                "insights_8": CURSOR_ID,
                "insights_9": 7,
            },
            query,
            params,
        )


# ============================================================================
# make_signature_groups_query
# ============================================================================


class TestSignatureGroupsQuery:
    @pytest.mark.parametrize(
        ("lens", "group_by", "group_exprs", "group_keys", "table"),
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
                "toDate(source_started_at) AS day",
                "day",
                "intent_signatures",
                id="day_groups_on_its_alias",
            ),
            pytest.param(
                "intent",
                ["category", "agent_name", "day"],
                "category, agent_name, toDate(source_started_at) AS day",
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
                id="sentiment_on_the_intent_lens",
            ),
            pytest.param(
                "failure",
                ["severity"],
                "severity",
                "severity",
                "failure_signatures",
                id="severity_on_the_failure_lens",
            ),
            pytest.param(
                "failure",
                ["agent_name"],
                "agent_name",
                "agent_name",
                "failure_signatures",
                id="a_shared_field_on_the_failure_lens",
            ),
        ],
    )
    def test_group_by(
        self,
        lens: str,
        group_by: list[str],
        group_exprs: str,
        group_keys: str,
        table: str,
    ) -> None:
        query, params = build_groups(
            rows_req(lens=lens, mode="groups", group_by=group_by)
        )
        expected = expected_groups_sql(
            group_exprs=group_exprs,
            table=table,
            where=BASE_WHERE,
            group_keys=group_keys,
            limit_slot="{insights_3:UInt32}",
        )
        assert_sql(expected, {**BASE_PARAMS, "insights_3": 100}, query, params)

    def test_filters_apply_to_groups_the_same_way(self) -> None:
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

    def test_a_cursor_never_reaches_a_grouped_read(self) -> None:
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

    @pytest.mark.parametrize("lens", ["intent", "failure"])
    def test_measures_never_sum_or_plain_count(self, lens: str) -> None:
        """Failure windows overlap on a turn, so `sum` would double-count, and
        `count()` would inflate on an unmerged replacement row.
        """
        query, _ = build_groups(rows_req(lens=lens, mode="groups"))
        assert "sum(" not in query
        assert "count()" not in query
        assert "uniqExact(id) AS occurrences" in query


# ============================================================================
# Validation: every raising branch
# ============================================================================


class TestValidation:
    @pytest.mark.parametrize(
        ("lens", "field", "valid_on"),
        [
            pytest.param("failure", "sentiment", "intent", id="sentiment_on_failure"),
            pytest.param("intent", "severity", "failure", id="severity_on_intent"),
        ],
    )
    def test_a_lens_only_group_field_is_rejected_on_the_other_lens(
        self, lens: str, field: str, valid_on: str
    ) -> None:
        with pytest.raises(ValueError, match=f"only valid on the {valid_on} lens"):
            build_groups(rows_req(lens=lens, mode="groups", group_by=[field]))

    def test_groups_mode_requires_a_group_field(self) -> None:
        with pytest.raises(ValueError, match="at least one group_by field"):
            build_groups(rows_req(mode="groups", group_by=[]))

    def test_an_unknown_group_field_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown insights group field"):
            build_groups(unvalidated_rows_req(mode="groups", group_by=["not_a_field"]))

    @pytest.mark.parametrize("build", [build_rows, build_groups])
    def test_an_unknown_lens_is_rejected(self, build) -> None:
        with pytest.raises(ValueError, match="unknown insights lens"):
            build(unvalidated_rows_req(lens="sideways", mode="groups"))

    def test_an_unknown_row_order_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown insights row order"):
            build_rows(unvalidated_rows_req(order="sideways"))


# ============================================================================
# Contracts the builder shares with its callers
# ============================================================================


class TestBuilderContracts:
    def test_no_caller_value_reaches_the_sql_text(self) -> None:
        """Parameters only: every value lands in params, never inline in the SQL."""
        hostile = "' OR 1=1 --"
        query, params = build_rows(
            rows_req(
                project_id=hostile,
                turn_trace_id=hostile,
                conversation_id=hostile,
                categories=[hostile],
                signature_hashes=[hostile],
                order="key",
                cursor=InsightSignatureCursor(day=MID_DAY, id=CURSOR_ID),
            )
        )
        assert hostile not in query
        assert hostile in params.values()
        assert [hostile.upper()] in params.values()

    def test_no_caller_value_reaches_the_context_sql_text(self) -> None:
        hostile = "' OR 1=1 --"
        query, params = build_context(
            context_req(
                project_id=hostile, conversation_id=hostile, turn_trace_ids=[hostile]
            )
        )
        assert hostile not in query
        assert hostile in params.values()
        assert [hostile] in params.values()

    @pytest.mark.parametrize("lens", ["intent", "failure"])
    def test_every_selected_column_is_a_field_on_the_row_model(self, lens: str) -> None:
        """The handler hydrates rows by keyword, so an alias with no field breaks it."""
        lens_columns = INTENT_ROW_COLUMNS if lens == "intent" else FAILURE_ROW_COLUMNS
        aliases = [
            column.split(" AS ")[-1]
            for column in (*SHARED_ROW_COLUMNS, *lens_columns, "vector")
        ]
        assert set(aliases) <= set(InsightSignatureRow.model_fields)

    def test_the_context_projection_covers_its_model_plus_the_dedupe_columns(
        self,
    ) -> None:
        """`lens` and every payload field come from the SELECT; `id` and
        `inserted_at` are there only so the handler can collapse versions.
        """
        assert set(InsightContextSignature.model_fields) <= set(CONTEXT_COLUMNS)
        assert set(CONTEXT_COLUMNS) - set(InsightContextSignature.model_fields) == {
            "id",
            "inserted_at",
        }

    def test_every_group_field_exposes_an_alias_the_handler_can_read(self) -> None:
        """`_group` looks each value up by field name, or by `day` for the expr."""
        for field, expression in GROUP_EXPRESSIONS.items():
            alias = expression.split(" AS ")[-1]
            assert alias == ("day" if field == "day" else field)

    def test_neither_lens_reorders_the_shared_projection_prefix(self) -> None:
        """The shared columns are pinned identical by the migration's own test;
        here it is that neither lens drops or reorders that prefix.
        """
        intent, _ = build_rows(rows_req(lens="intent"))
        failure, _ = build_rows(rows_req(lens="failure"))
        assert f"SELECT {SHARED_COLS}," in intent
        assert f"SELECT {SHARED_COLS}," in failure

    def test_no_read_uses_final(self) -> None:
        """Version collapse is per-read by design: `uniqExact`, or the caller
        deduping a page. `FINAL` on these tables is always a mistake.
        """
        queries = [
            build_rows(rows_req())[0],
            build_rows(rows_req(lens="failure", order="key"))[0],
            build_groups(rows_req(mode="groups"))[0],
            build_context(context_req())[0],
        ]
        for query in queries:
            assert "FINAL" not in query.upper()
