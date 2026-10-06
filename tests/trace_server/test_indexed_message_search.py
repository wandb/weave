from datetime import datetime, timedelta, timezone

import pytest

from weave.shared.errors import InvalidRequest
from weave.trace_server.agents.types import AgentSearchReq
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.message_search_query_builder import (
    MessageSearch,
    make_indexed_message_search_query,
    parse_message_search,
)

pytestmark = pytest.mark.trace_server
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", MessageSearch((), ())),
        ("acoustic **guitar** acoustic", MessageSearch(("acoustic", "guitar"), ())),
        (
            'warm "acoustic guitar"',
            MessageSearch(("warm", "acoustic", "guitar"), ("acoustic guitar",)),
        ),
        (
            '"one two" "three four"',
            MessageSearch(("one", "two", "three", "four"), ("one two", "three four")),
        ),
        (r"hello \"world\"", MessageSearch(("hello", "world"), ())),
        ("café 東京", MessageSearch(("café", "東京"), ())),
    ],
)
def test_parse_message_search(query, expected):
    assert parse_message_search(query) == expected


@pytest.mark.parametrize("query", ['"unfinished', '""', '"**"', "**", "   "])
def test_invalid_message_search(query):
    with pytest.raises(InvalidRequest):
        parse_message_search(query)


def _insert(ch_server, body="acoustic guitar", **overrides):
    values = {
        "project": "p",
        "body": body,
        "span": "span",
        "trace": "trace",
        "conversation": "conv",
        "role": "user",
        "started": START,
        "created": START,
        "agent": "agent",
        "provider": "provider",
        "model": "model",
        "expiry": datetime(2099, 1, 1),
    }
    values.update(overrides)
    ch_server.ch_client.command(
        """INSERT INTO messages (
        project_id, content_digest, content, span_id, trace_id, conversation_id, role,
        started_at, created_at, agent_name, provider_name, request_model, expire_at)
        SELECT {project:String}, murmurHash3_128({body:String}), {body:String},
               {span:String}, {trace:String}, {conversation:String}, {role:String},
               {started:DateTime64(6)}, {created:DateTime64(3)}, {agent:String},
               {provider:String}, {model:String}, {expiry:DateTime}
    """,
        parameters=values,
    )


def _search(ch_server, *, stable_metadata=False, **kwargs):
    pb = ParamBuilder("search")
    req = AgentSearchReq(project_id="p", **kwargs)
    sql = make_indexed_message_search_query(pb, req, stable_metadata=stable_metadata)
    return list(
        ch_server.ch_client.query(sql, parameters=pb.get_params()).named_results()
    )


@pytest.mark.parametrize("stable_metadata", [False, True])
def test_words_phrases_markdown_and_case(ch_server, stable_metadata):
    _insert(ch_server, "warm **acoustic** guitar", span="a")
    _insert(ch_server, "guitar with acoustic warmth", span="b")
    _insert(ch_server, "Acoustic guitar", span="c")
    _insert(ch_server, "warm **acoustic** guitar", project="another", span="leak")
    assert [
        r["span_id"]
        for r in _search(
            ch_server, query="acoustic guitar", stable_metadata=stable_metadata
        )
    ] == ["b", "a"]
    assert [
        r["span_id"]
        for r in _search(
            ch_server, query='"acoustic guitar"', stable_metadata=stable_metadata
        )
    ] == ["a"]
    assert [
        r["span_id"]
        for r in _search(
            ch_server, query='warm "acoustic guitar"', stable_metadata=stable_metadata
        )
    ] == ["a"]
    assert _search(ch_server, query="guit", stable_metadata=stable_metadata) == []


@pytest.mark.parametrize("stable_metadata", [False, True])
def test_collapse_filter_order_and_pagination(ch_server, stable_metadata):
    _insert(ch_server, span="old", started=START)
    _insert(ch_server, span="new", started=START + timedelta(seconds=1))
    _insert(
        ch_server,
        span="other",
        conversation="other",
        started=START + timedelta(seconds=2),
    )
    _insert(
        ch_server, span="end", conversation="end", started=START + timedelta(seconds=3)
    )
    kwargs = {
        "query": "guitar",
        "started_after": START,
        "started_before": START + timedelta(seconds=3),
        "stable_metadata": stable_metadata,
    }
    rows = _search(ch_server, **kwargs, limit=1)
    assert [(r["span_id"], r["conversation_id"], r["content"]) for r in rows] == [
        ("other", "other", "acoustic guitar")
    ]
    assert [r["span_id"] for r in _search(ch_server, **kwargs, limit=1, offset=1)] == [
        "new"
    ]
    assert _search(ch_server, **kwargs, limit=0) == []
    assert [
        r["span_id"]
        for r in _search(
            ch_server,
            **kwargs,
            conversation_id="conv",
            agent_name="agent",
            provider_name="provider",
            request_model="model",
            trace_id="trace",
            roles=["user"],
        )
    ] == ["new"]
    assert _search(ch_server, **kwargs, provider_name="absent") == []
    assert [
        r["span_id"]
        for r in _search(
            ch_server, query="guitar", started_before=START + timedelta(seconds=1)
        )
    ] == ["old"]


def test_structured_retrieval_preserves_spans_and_full_content(ch_server):
    body = "acoustic " + "x" * 600
    _insert(ch_server, body, span="a")
    _insert(ch_server, body, span="b")
    rows = _search(ch_server, query="", trace_id="trace", truncate_content=False)
    assert [(r["span_id"], r["content"]) for r in rows] == [("b", body), ("a", body)]
    assert [
        (r["span_id"], r["content"]) for r in _search(ch_server, query="acoustic")
    ] == [("b", body[:500])]


def test_latest_metadata_before_filtering_and_collapsing(ch_server):
    client = ch_server.ch_client
    client.command("SYSTEM STOP MERGES message_occurrences")
    client.command("SYSTEM STOP MERGES message_content")
    try:
        _insert(ch_server, conversation="", provider="old", created=START)
        _insert(
            ch_server,
            conversation="new",
            provider="new",
            created=START + timedelta(seconds=1),
        )
        assert [
            (r["span_id"], r["conversation_id"])
            for r in _search(ch_server, query="guitar")
        ] == [("span", "new")]
        assert _search(ch_server, query="guitar", provider_name="old") == []
        assert len(_search(ch_server, query="guitar", stable_metadata=True)) == 2
    finally:
        client.command("SYSTEM START MERGES message_content")
        client.command("SYSTEM START MERGES message_occurrences")


def test_roles_fallback_keys_and_expiry(ch_server):
    _insert(ch_server, role="tool_call", span="a", conversation="", trace="a")
    _insert(ch_server, role="tool_result", span="b", conversation="", trace="a")
    _insert(ch_server, role="tool_call", span="c", conversation="", trace="b")
    _insert(
        ch_server,
        role="tool_call",
        span="d",
        conversation="",
        trace="",
        expiry=datetime(2020, 1, 1),
    )
    _insert(ch_server, role="tool_call", span="e", conversation="", trace="")
    assert [
        r["span_id"] for r in _search(ch_server, query="guitar", roles=["tool"])
    ] == ["e", "c", "b", "a"]


def test_unicode_tokens_agree_with_clickhouse(ch_server):
    text = "café 東京 bold_你好"
    assert (
        tuple(
            ch_server.ch_client.query(
                "SELECT splitByNonAlpha({text:String})", parameters={"text": text}
            ).first_row[0]
        )
        == parse_message_search(text).tokens
    )
    _insert(ch_server, text)
    assert [r["content"] for r in _search(ch_server, query="café 東京")] == [text]
