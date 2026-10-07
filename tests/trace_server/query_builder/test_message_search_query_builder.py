from datetime import datetime

import pytest

from tests.trace_server.query_builder.utils import assert_raw_sql
from weave.shared.errors import InvalidRequest
from weave.trace_server.agents.types import AgentSearchReq
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.message_search_query_builder import (
    make_indexed_message_search_query,
)


def test_filtered_phrase_search_sql() -> None:
    pb = ParamBuilder("search")
    started_after = datetime(2026, 1, 1)
    started_before = datetime(2026, 2, 1)
    query = make_indexed_message_search_query(
        pb,
        AgentSearchReq(
            project_id="p",
            query='warm "acoustic guitar"',
            trace_id="trace",
            roles=["tool", "user", "tool_call"],
            started_after=started_after,
            started_before=started_before,
            agent_name="agent",
            provider_name="provider",
            request_model="model",
            conversation_id="conversation",
            limit=10,
            offset=20,
        ),
    )
    expected = """
        WITH page AS MATERIALIZED (
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content_digest, started_at, created_at
            FROM message_occurrences FINAL
            PREWHERE project_id = {search_0:String}
                AND trace_id = {search_1:String}
                AND role IN {search_2:Array(String)}
                AND started_at >= {search_3:DateTime64(6)}
                AND started_at < {search_4:DateTime64(6)}
                AND content_digest GLOBAL IN (
                    SELECT content_digest FROM message_content
                    WHERE project_id = {search_9:String}
                        AND hasAllTokens(content, {search_12:Array(String)})
                        AND hasSubstr(tokens(content, 'splitByNonAlpha'),
                            tokens({search_13:String}, 'splitByNonAlpha'))
                )
            WHERE agent_name = {search_5:String}
                AND provider_name = {search_6:String}
                AND request_model = {search_7:String}
                AND conversation_id = {search_8:String}
                AND expire_at > now()
            ORDER BY started_at DESC, span_id DESC, trace_id DESC,
                     role DESC, content_digest DESC, created_at DESC
            LIMIT 1 BY if(conversation_id != '', concat('c:', conversation_id),
                if(trace_id != '', concat('t:', trace_id), concat('s:', span_id))),
                role, content_digest
            LIMIT {search_10:UInt64} OFFSET {search_11:UInt64}
        )
        SELECT p.conversation_id AS conversation_id,
               p.conversation_name AS conversation_name,
               p.agent_name AS agent_name, p.span_id AS span_id,
               p.trace_id AS trace_id, p.role AS role, c.content AS content,
               lower(hex(p.content_digest)) AS content_digest,
               p.started_at AS started_at
        FROM page AS p
        GLOBAL INNER ALL JOIN (
            SELECT content_digest, any(substring(content, 1, 500)) AS content
            FROM message_content
            WHERE project_id = {search_9:String}
                AND content_digest GLOBAL IN (SELECT content_digest FROM page)
            GROUP BY content_digest
        ) AS c ON p.content_digest = c.content_digest
        ORDER BY p.started_at DESC, p.span_id DESC, p.trace_id DESC,
                 p.role DESC, p.content_digest DESC, p.created_at DESC
        SETTINGS enable_materialized_cte = 1, optimize_move_to_prewhere_if_final = 0,
                 do_not_merge_across_partitions_select_final = 1
    """
    expected_params = {
        "search_0": "p",
        "search_1": "trace",
        "search_2": ["tool_call", "tool_result", "user"],
        "search_3": started_after,
        "search_4": started_before,
        "search_5": "agent",
        "search_6": "provider",
        "search_7": "model",
        "search_8": "conversation",
        "search_9": "p",
        "search_10": 10,
        "search_11": 20,
        "search_12": ["warm", "acoustic", "guitar"],
        "search_13": "acoustic guitar",
    }
    assert_raw_sql(query, expected, pb.get_params(), expected_params)


@pytest.mark.parametrize(
    ("text", "tokens", "phrases"),
    [
        ("acoustic **guitar** acoustic", ["acoustic", "guitar"], []),
        ('"**acoustic** guitar"', ["acoustic", "guitar"], ["**acoustic** guitar"]),
        ('"very very warm"', ["very", "warm"], ["very very warm"]),
        (
            '"one two" "three four"',
            ["one", "two", "three", "four"],
            ["one two", "three four"],
        ),
        (r"hello \"world\"", ["hello", "world"], []),
        ("café 東京", ["café", "東京"], []),
    ],
)
def test_search_terms_are_bound_parameters(
    text: str, tokens: list[str], phrases: list[str]
) -> None:
    pb = ParamBuilder("search")
    query = make_indexed_message_search_query(
        pb, AgentSearchReq(project_id="p", query=text)
    )
    phrase_predicates = " ".join(
        "AND hasSubstr(tokens(content, 'splitByNonAlpha'), "
        f"tokens({{search_{i}:String}}, 'splitByNonAlpha'))"
        for i in range(5, 5 + len(phrases))
    )
    expected = f"""
        WITH page AS MATERIALIZED (
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content_digest, started_at, created_at
            FROM message_occurrences FINAL
            PREWHERE project_id = {{search_0:String}}
                AND content_digest GLOBAL IN (
                    SELECT content_digest FROM message_content
                    WHERE project_id = {{search_1:String}}
                        AND hasAllTokens(content, {{search_4:Array(String)}})
                        {phrase_predicates}
                )
            WHERE expire_at > now()
            ORDER BY started_at DESC, span_id DESC, trace_id DESC,
                     role DESC, content_digest DESC, created_at DESC
            LIMIT 1 BY if(conversation_id != '', concat('c:', conversation_id),
                if(trace_id != '', concat('t:', trace_id), concat('s:', span_id))),
                role, content_digest
            LIMIT {{search_2:UInt64}} OFFSET {{search_3:UInt64}}
        )
        SELECT p.conversation_id AS conversation_id,
               p.conversation_name AS conversation_name,
               p.agent_name AS agent_name, p.span_id AS span_id,
               p.trace_id AS trace_id, p.role AS role, c.content AS content,
               lower(hex(p.content_digest)) AS content_digest,
               p.started_at AS started_at
        FROM page AS p
        GLOBAL INNER ALL JOIN (
            SELECT content_digest, any(substring(content, 1, 500)) AS content
            FROM message_content
            WHERE project_id = {{search_1:String}}
                AND content_digest GLOBAL IN (SELECT content_digest FROM page)
            GROUP BY content_digest
        ) AS c ON p.content_digest = c.content_digest
        ORDER BY p.started_at DESC, p.span_id DESC, p.trace_id DESC,
                 p.role DESC, p.content_digest DESC, p.created_at DESC
        SETTINGS enable_materialized_cte = 1, optimize_move_to_prewhere_if_final = 0,
                 do_not_merge_across_partitions_select_final = 1
    """
    expected_params = {
        "search_0": "p",
        "search_1": "p",
        "search_2": 20,
        "search_3": 0,
        "search_4": tokens,
    }
    for i, phrase in enumerate(phrases, start=5):
        expected_params[f"search_{i}"] = phrase
    assert_raw_sql(query, expected, pb.get_params(), expected_params)


@pytest.mark.parametrize("truncate_content", [True, False])
def test_empty_search_preserves_spans_and_content_selection(
    truncate_content: bool,
) -> None:
    pb = ParamBuilder("search")
    query = make_indexed_message_search_query(
        pb,
        AgentSearchReq(
            project_id="p",
            query="",
            trace_id="trace",
            truncate_content=truncate_content,
            limit=5,
            offset=10,
        ),
    )
    content = "substring(content, 1, 500)" if truncate_content else "content"
    expected = f"""
        WITH page AS MATERIALIZED (
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content_digest, started_at, created_at
            FROM message_occurrences FINAL
            PREWHERE project_id = {{search_0:String}} AND trace_id = {{search_1:String}}
            WHERE expire_at > now()
            ORDER BY started_at DESC, span_id DESC, trace_id DESC,
                     role DESC, content_digest DESC, created_at DESC
            LIMIT {{search_3:UInt64}} OFFSET {{search_4:UInt64}}
        )
        SELECT p.conversation_id AS conversation_id,
               p.conversation_name AS conversation_name,
               p.agent_name AS agent_name, p.span_id AS span_id,
               p.trace_id AS trace_id, p.role AS role, c.content AS content,
               lower(hex(p.content_digest)) AS content_digest,
               p.started_at AS started_at
        FROM page AS p
        GLOBAL INNER ALL JOIN (
            SELECT content_digest, any({content}) AS content
            FROM message_content
            WHERE project_id = {{search_2:String}}
                AND content_digest GLOBAL IN (SELECT content_digest FROM page)
            GROUP BY content_digest
        ) AS c ON p.content_digest = c.content_digest
        ORDER BY p.started_at DESC, p.span_id DESC, p.trace_id DESC,
                 p.role DESC, p.content_digest DESC, p.created_at DESC
        SETTINGS enable_materialized_cte = 1, optimize_move_to_prewhere_if_final = 0,
                 do_not_merge_across_partitions_select_final = 1
    """
    expected_params = {
        "search_0": "p",
        "search_1": "trace",
        "search_2": "p",
        "search_3": 5,
        "search_4": 10,
    }
    assert_raw_sql(query, expected, pb.get_params(), expected_params)


@pytest.mark.parametrize("text", ['"unfinished', '""', '"**"', "**", "   "])
def test_invalid_search_is_rejected_before_building_sql(text: str) -> None:
    pb = ParamBuilder("search")
    with pytest.raises(InvalidRequest):
        make_indexed_message_search_query(
            pb, AgentSearchReq(project_id="p", query=text)
        )
    assert pb.get_params() == {}
