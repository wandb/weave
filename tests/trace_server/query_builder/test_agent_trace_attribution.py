"""Unit tests for read-time trace attribution of agent / conversation identity.

`attributed_spans_source` is the single place the four identity columns get
their trace-inherited value; the builders just swap it in for `FROM spans`.
These tests pin its SQL shape and the `references_identity` gating helpers.
"""

import datetime
import re

from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_trace_attribution import (
    IDENTITY_COLUMNS,
    attributed_spans_source,
    fields_reference_identity,
    query_references_identity,
    query_references_trace_id,
)


def _fmt(sql: str) -> str:
    """Normalize whitespace (incl. around punctuation) to ignore formatting."""
    return re.sub(r"\s*([(),])\s*", r"\1", " ".join(sql.split()))


def test_identity_columns_are_the_four_inheriting_fields() -> None:
    assert set(IDENTITY_COLUMNS) == {
        "agent_name",
        "agent_version",
        "agent_id",
        "conversation_id",
    }


def test_attributed_source_inherits_agent_triple_coherently() -> None:
    pb = ParamBuilder("genai")
    sql = attributed_spans_source(
        pb, project_id="p1", started_after=None, started_before=None
    )
    # agent_name / agent_version / agent_id inherit together as one tuple taken
    # from a single span (argMinIf by started_at, gated on agent_name), so a
    # span's inherited identity can never mix two agents. A span that declares
    # its own agent_name keeps its entire own triple. conversation_id is
    # inherited on its own.
    expected = """
        (SELECT * EXCEPT (agent_name, agent_version, agent_id, conversation_id,
                          has_own_agent_identity, fb_agent_identity, fb_conversation_id),
            if(has_own_agent_identity, agent_name, fb_agent_identity.1) AS agent_name,
            if(has_own_agent_identity, agent_version, fb_agent_identity.2) AS agent_version,
            if(has_own_agent_identity, agent_id, fb_agent_identity.3) AS agent_id,
            if(conversation_id != '', conversation_id, fb_conversation_id) AS conversation_id
         FROM (
           SELECT s0.*, (s0.agent_name != '') AS has_own_agent_identity,
                  tf.fb_agent_identity, tf.fb_conversation_id
           FROM spans s0
           LEFT JOIN (
             SELECT trace_id,
                 argMinIf((agent_name, agent_version, agent_id), started_at, agent_name != '')
                   AS fb_agent_identity,
                 anyIf(conversation_id, conversation_id != '') AS fb_conversation_id
             FROM spans
             WHERE project_id = {genai_0:String}
             GROUP BY trace_id) tf ON s0.trace_id = tf.trace_id
           WHERE s0.project_id = {genai_0:String}))
    """
    assert _fmt(sql) == _fmt(expected)
    assert pb.get_params() == {"genai_0": "p1"}


def test_attributed_source_scopes_fallback_to_trace_ids() -> None:
    # The page-prefetch two-pass feeds the limited page as `base_relation` and
    # restricts the fallback rollup to the page's trace_ids. Scoping is lossless
    # because the rollup is consumed only via the trace_id join.
    pb = ParamBuilder("genai")
    sql = attributed_spans_source(
        pb,
        project_id="p1",
        started_after=None,
        started_before=None,
        base_relation="page",
        scope_fallback_to_base=True,
    )
    expected = """
        (SELECT * EXCEPT (agent_name, agent_version, agent_id, conversation_id,
                          has_own_agent_identity, fb_agent_identity, fb_conversation_id),
            if(has_own_agent_identity, agent_name, fb_agent_identity.1) AS agent_name,
            if(has_own_agent_identity, agent_version, fb_agent_identity.2) AS agent_version,
            if(has_own_agent_identity, agent_id, fb_agent_identity.3) AS agent_id,
            if(conversation_id != '', conversation_id, fb_conversation_id) AS conversation_id
         FROM (
           SELECT s0.*, (s0.agent_name != '') AS has_own_agent_identity,
                  tf.fb_agent_identity, tf.fb_conversation_id
           FROM page s0
           LEFT JOIN (
             SELECT trace_id,
                 argMinIf((agent_name, agent_version, agent_id), started_at, agent_name != '')
                   AS fb_agent_identity,
                 anyIf(conversation_id, conversation_id != '') AS fb_conversation_id
             FROM spans
             WHERE project_id = {genai_0:String} AND trace_id IN (SELECT trace_id FROM page)
             GROUP BY trace_id) tf ON s0.trace_id = tf.trace_id
           WHERE s0.project_id = {genai_0:String}))
    """
    assert _fmt(sql) == _fmt(expected)
    assert pb.get_params() == {"genai_0": "p1"}


def test_attributed_source_bounds_fallback_scan_with_slack() -> None:
    after = datetime.datetime(2026, 1, 10, tzinfo=datetime.timezone.utc)
    before = datetime.datetime(2026, 1, 11, tzinfo=datetime.timezone.utc)
    pb = ParamBuilder("genai")
    sql = attributed_spans_source(
        pb, project_id="p1", started_after=after, started_before=before
    )
    params = pb.get_params()
    # Inner base scan uses the exact window; the fallback scan widens it by one
    # trace-duration of slack on each side so edge spans still resolve.
    slack = datetime.timedelta(hours=1)
    assert after - slack in params.values()
    assert before + slack in params.values()
    assert after in params.values()
    assert before in params.values()
    assert (
        "argMinIf((agent_name, agent_version, agent_id), started_at, agent_name != '')"
        in sql
    )


def test_query_references_identity_resolves_aliases() -> None:
    def q(field: str) -> Query:
        return Query.model_validate(
            {"$expr": {"$eq": [{"$getField": field}, {"$literal": "x"}]}}
        )

    assert query_references_identity(q("agent.name"))
    assert query_references_identity(q("gen_ai.agent.name"))
    assert query_references_identity(q("agent_name"))
    assert query_references_identity(q("conversation_id"))
    assert not query_references_identity(q("operation_name"))
    assert not query_references_identity(None)


def test_fields_reference_identity() -> None:
    assert fields_reference_identity(["agent.version"])
    assert fields_reference_identity(["operation_name", "agent_id"])
    assert not fields_reference_identity(["operation_name", "request_model"])
    assert not fields_reference_identity([])


def test_query_references_trace_id() -> None:
    def q(field: str) -> Query:
        return Query.model_validate(
            {"$expr": {"$eq": [{"$getField": field}, {"$literal": "x"}]}}
        )

    assert query_references_trace_id(q("trace_id"))
    assert not query_references_trace_id(q("operation_name"))
    assert not query_references_trace_id(q("agent_name"))
    assert not query_references_trace_id(None)
