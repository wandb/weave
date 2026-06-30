from weave.shared import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.feedback import resolve_feedback_conversation_id
from weave.trace_server.trace_server_common import (
    FEEDBACK_QUERY_FIELDS,
    group_agent_feedback_by_target,
    make_agent_feedback_query_req,
    make_feedback_query_req,
)


def _extract_ref_literals(req) -> list[str]:
    expr = req.query.model_dump(by_alias=True)["$expr"]
    return [lit["$literal"] for lit in expr["$in"][1]]


def test_feedback_query_fields_include_typed_scorer_columns():
    """Calls/agent-chat feedback hydration goes through FEEDBACK_QUERY_FIELDS.
    The typed scorer columns must be in this list or wandb.agent_monitor
    rows surface to the UI without their tags/ratings/reasons/confidences.
    """
    typed_columns = (
        "scorer_tags",
        "scorer_tag_reasons",
        "scorer_tag_confidences",
        "scorer_ratings",
        "scorer_rating_reasons",
        "scorer_rating_confidences",
    )
    for column in typed_columns:
        assert column in FEEDBACK_QUERY_FIELDS

    # Both helpers must request these columns — they're the two paths that
    # fold feedback into calls / agent chat responses.
    calls_req = make_feedback_query_req(
        project_id="p", calls=[{"project_id": "p", "id": "c1"}]
    )
    agent_req = make_agent_feedback_query_req(project_id="p", refs=[])
    for column in typed_columns:
        assert column in calls_req.fields
        assert column in agent_req.fields


def test_make_agent_feedback_query_req_unions_arbitrary_ref_kinds():
    refs = [
        ri.InternalAgentTurnRef(
            project_id="p", trace_id="0123456789abcdef0123456789abcdef"
        ).uri,
        ri.InternalAgentConversationRef(project_id="p", conversation_id="sess-1").uri,
        ri.InternalAgentSpanRef(project_id="p", span_id="0123456789abcdef").uri,
        ri.InternalCallRef(project_id="p", id="call-xyz").uri,
    ]

    req = make_agent_feedback_query_req(project_id="p", refs=refs)

    assert req.project_id == "p"
    assert _extract_ref_literals(req) == refs


def test_group_agent_feedback_by_target_separates_kinds_and_skips_non_agent_refs():
    feedback = tsi.FeedbackQueryRes(
        result=[
            {
                "id": "f1",
                "weave_ref": ri.InternalAgentTurnRef(project_id="p", trace_id="t1").uri,
            },
            {
                "id": "f2",
                "weave_ref": ri.InternalAgentTurnRef(project_id="p", trace_id="t1").uri,
            },
            {
                "id": "f3",
                "weave_ref": ri.InternalAgentConversationRef(
                    project_id="p", conversation_id="c1"
                ).uri,
            },
            {
                "id": "f4",
                "weave_ref": ri.InternalAgentSpanRef(project_id="p", span_id="s1").uri,
            },
            {
                "id": "f5",
                "weave_ref": ri.InternalCallRef(project_id="p", id="call-xyz").uri,
            },
        ]
    )

    groups = group_agent_feedback_by_target(feedback)

    assert [item["id"] for item in groups.by_trace_id["t1"]] == ["f1", "f2"]
    assert [item["id"] for item in groups.by_conversation_id["c1"]] == ["f3"]
    assert [item["id"] for item in groups.by_span_id["s1"]] == ["f4"]


def test_resolve_feedback_conversation_id():
    pid = "entproj"
    conv_uri = ri.InternalAgentConversationRef(project_id=pid, conversation_id="c1").uri()
    turn_uri = ri.InternalAgentTurnRef(project_id=pid, trace_id="t1").uri()
    span_uri = ri.InternalAgentSpanRef(project_id=pid, span_id="s1").uri()

    def lookup(trace_id: str, span_id: str) -> str:
        return {("t1", ""): "c-from-turn", ("", "s1"): "c-from-span"}.get((trace_id, span_id), "")

    cases = [
        # (weave_ref, supplied, expected)
        (conv_uri, "", "c1"),
        (turn_uri, "", "c-from-turn"),
        (span_uri, "", "c-from-span"),
        (turn_uri, "explicit", "explicit"),   # caller wins
        ("weave-trace-internal:///ent/proj/call/x", "", ""),  # non-agent ref
    ]
    for weave_ref, supplied, expected in cases:
        assert resolve_feedback_conversation_id(weave_ref, supplied, lookup) == expected
