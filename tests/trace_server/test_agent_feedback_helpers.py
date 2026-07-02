from weave.shared import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.feedback import (
    ResolvedAgentTargets,
    resolve_feedback_agent_targets,
)
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


def test_resolve_feedback_agent_targets():
    pid = "entproj"
    conv_uri = ri.InternalAgentConversationRef(project_id=pid, conversation_id="c1").uri()
    turn_uri = ri.InternalAgentTurnRef(project_id=pid, trace_id="t1").uri()
    span_uri = ri.InternalAgentSpanRef(project_id=pid, span_id="s1").uri()

    cases = [
        # (weave_ref, supplied_conversation_id, supplied_trace_id, expected)
        # conversation ref: conversation from the ref, no single turn
        (conv_uri, "", "", ResolvedAgentTargets("c1", "")),
        # turn ref: trace from the ref; conversation must be supplied (no lookup)
        (turn_uri, "", "", ResolvedAgentTargets("", "t1")),
        # turn ref + caller-supplied conversation: both set
        (turn_uri, "c-sup", "", ResolvedAgentTargets("c-sup", "t1")),
        # span ref: nothing derivable from the ref alone; rely on caller-supplied
        (span_uri, "", "", ResolvedAgentTargets("", "")),
        (span_uri, "c-sup", "t-sup", ResolvedAgentTargets("c-sup", "t-sup")),
        # caller-supplied values win entirely (ref not consulted)
        (
            turn_uri,
            "explicit-conv",
            "explicit-trace",
            ResolvedAgentTargets("explicit-conv", "explicit-trace"),
        ),
        # `call` is a known ref kind; parse_internal_uri returns InternalCallRef and
        # the resolver falls through, leaving both ids unset.
        ("weave-trace-internal:///ent/proj/call/x", "", "", ResolvedAgentTargets("", "")),
        # Completely invalid scheme — parse_internal_uri raises InvalidInternalRef;
        # this covers the `except InvalidInternalRef` branch.
        ("not-a-valid-ref:///whatever", "", "", ResolvedAgentTargets("", "")),
    ]
    for weave_ref, sup_conv, sup_trace, expected in cases:
        assert (
            resolve_feedback_agent_targets(weave_ref, sup_conv, sup_trace) == expected
        )
