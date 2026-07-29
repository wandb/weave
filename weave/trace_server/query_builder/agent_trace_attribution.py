"""Read-time trace attribution for agent-identity columns.

Agent identity (`agent_name` / `agent_version` / `agent_id`) and conversation
identity (`conversation_id`) are typically reported only on the `invoke_agent`
span, not on the child llm / tool spans it encloses. A span-exact read of those
columns therefore shows blank identity on every child span and undercounts the
turn's real work.

This module attributes that identity at *read time* with a three-step rule,
checked in order:

    1. if a span declares its own agent (`agent_name != ''`), use its own
       identity (singleton / span-exact);
    2. otherwise, if the span's immediate parent declares its own agent, inherit
       that parent's identity (the common case for a tool/llm span that is a
       direct child of the `invoke_agent` span that issued it, including a
       *sub*-agent's `invoke_agent` span);
    3. otherwise inherit the trace's earliest-declared agent.

It is expressed by wrapping the `spans` table in an *attributed-spans*
subquery (see :func:`attributed_spans_source`). Callers swap their
`FROM spans s` for `FROM {attributed_spans_source(...)} s` and every
downstream reference to `s.agent_name` (filter, GROUP BY, projection,
aggregate) transparently sees the attributed value — what you filter on equals
what you display.

`agent_name` / `agent_version` / `agent_id` identify one agent, so they
are inherited *together* as a single tuple taken from one span — either the
span's immediate parent (step 2) or, failing that, the earliest span in the
trace that declares an `agent_name` (`argMinIf` by `started_at`, step 3).
Picking each column independently could synthesize a `(name, version)` pair
that never co-occurred on any real span. Likewise, a span that declares its
own `agent_name` keeps its *entire* own triple, so its version / id are never
crossed with an inherited agent's. `conversation_id` is trace-scoped and
inherited on its own (step 3 only; it has no per-parent step).

Step 2 is a *one-hop* parent lookup, not a full nearest-enclosing-agent walk:
a span separated from its owning agent by an identity-less intermediate span
still falls through to step 3's flat, trace-wide fallback. That is a known,
documented limitation, not a bug — it trades exact hierarchical resolution
(which would need an unbounded parent-chain walk ClickHouse cannot express
without a recursive CTE) for a bounded, single-scan fix that resolves the
common case: it never over-corrects, since step 2 only fires when the parent
itself declares an identity, and step 3 is unchanged for every span step 2
doesn't resolve. The full hierarchical "nearest enclosing agent" projection
used by the chat view lives in `weave.trace_server.agents.chat_view` and is
intentionally separate — queries that feed the chat view must NOT use this
source or they would double-attribute.
"""

from __future__ import annotations

import datetime

from weave.trace_server.agents import semconv
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder

# The identity columns that inherit from their trace when unset. Order is fixed
# so the generated SQL is stable (and snapshot-testable).
IDENTITY_COLUMNS: tuple[str, ...] = (
    "agent_name",
    "agent_version",
    "agent_id",
    "conversation_id",
)

_IDENTITY_COLUMN_SET = frozenset(IDENTITY_COLUMNS)

# `agent_name` / `agent_version` / `agent_id` identify one agent and are
# inherited together as a single tuple (see module docstring); `agent_name` is
# the marker for "this span declares its own agent". `conversation_id` is
# trace-scoped and inherited on its own.
_AGENT_IDENTITY_COLUMNS: tuple[str, ...] = ("agent_name", "agent_version", "agent_id")
_AGENT_IDENTITY_MARKER = "agent_name"

# All spans of a trace fall within one turn, so a span needing attribution is at
# most one trace-duration away from the identity-bearing span it inherits from.
# We widen the trace-fallback scan's window by this slack so an edge span still
# finds its identity-bearing span (which may have started just outside the outer
# window) while ClickHouse can still prune by the (project_id, started_at)
# primary key instead of scanning the project's whole history.
_TRACE_FALLBACK_WINDOW_SLACK = datetime.timedelta(hours=1)


def _collect_get_fields(node: object) -> set[str]:
    """Recursively collect every `$getField` name in a dumped Query expr."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$getField" and isinstance(value, str):
                found.add(value)
            else:
                found |= _collect_get_fields(value)
    elif isinstance(node, (list, tuple)):
        # Comparison operands (e.g. `$eq`) serialize as tuples, not lists.
        for item in node:
            found |= _collect_get_fields(item)
    return found


def _names_hit(names: set[str], columns: frozenset[str]) -> bool:
    return any(
        semconv.FILTERABLE_KEY_TO_COLUMN.get(name, name) in columns for name in names
    )


def query_references_identity(query: tsi_query.Query | None) -> bool:
    """Whether a Query filter references any trace-attributed identity column.

    Walks the dumped expression for `$getField` references and resolves each
    through semconv, so `agent.name` / `gen_ai.agent.name` / `agent_name`
    all count.
    """
    if query is None:
        return False
    names = _collect_get_fields(query.model_dump(by_alias=True))
    return _names_hit(names, _IDENTITY_COLUMN_SET)


def query_references_trace_id(query: tsi_query.Query | None) -> bool:
    """Whether a Query filter references `trace_id`, the trace-fallback join key.

    A `trace_id` filter is pushed by ClickHouse straight into the fallback
    rollup, so the current path is already optimal; the page-prefetch two-pass
    would only add a redundant scan.
    """
    if query is None:
        return False
    names = _collect_get_fields(query.model_dump(by_alias=True))
    return _names_hit(names, frozenset({"trace_id"}))


def fields_reference_identity(field_names: list[str]) -> bool:
    """Whether any public field name resolves to an identity column."""
    return _names_hit(set(field_names), _IDENTITY_COLUMN_SET)


def attributed_spans_source(
    pb: ParamBuilder,
    *,
    project_id: str,
    started_after: datetime.datetime | None,
    started_before: datetime.datetime | None,
    base_relation: str = "spans",
    fallback_scope_relation: str | None = None,
) -> str:
    """Return a parenthesized subquery that stands in for the `spans` table.

    The result exposes every column of `base_relation`, but the four identity
    columns carry their trace-attributed value (own value if set, else a
    per-trace `anyIf` fallback). The caller aliases it, e.g.
    `FROM {attributed_spans_source(...)} s`.

    `base_relation` is the relation the attributed columns are read from; it
    defaults to the raw `spans` table but may be any `spans`-shaped subquery
    (e.g. the cost-augmented source), in which case its extra columns pass
    through untouched. The per-trace fallback always scans the raw `spans`
    table since it only needs the identity columns and `trace_id`.

    `fallback_scope_relation`, when set, restricts the fallback rollup to the
    `trace_id`s of that relation (`trace_id IN (SELECT trace_id FROM
    {fallback_scope_relation})`). Since the fallback is consumed only via the
    `trace_id` join, scoping it to the join's trace_ids removes only rows the
    join would discard, so attributed values are unchanged. The page-prefetch
    two-pass list read passes its page CTE here to scope the rollup to the
    page's traces.

    `base_relation` and `fallback_scope_relation` are interpolated as raw SQL
    and must be trusted, internal fragments (a relation name / a literal
    subquery), never user input; user-derived values still flow through `pb`
    params.

    The inner scan is bounded to `project_id` and the outer time window so it
    prunes by primary key; the fallback scan is bounded to the same window
    widened by one trace-duration of slack so edge spans still resolve. The
    same fallback scan also builds a per-trace `span_id -> agent identity` map
    (restricted to identity-declaring spans, so it stays small) used to resolve
    a span's *immediate parent* identity in one map lookup, at no extra scan or
    join cost.
    """
    pid_slot = pb.add(project_id, param_type="String")

    fallback_conds = [f"project_id = {pid_slot}"]
    base_conds = [f"s0.project_id = {pid_slot}"]
    if fallback_scope_relation is not None:
        fallback_conds.append(
            f"trace_id IN (SELECT trace_id FROM {fallback_scope_relation})"
        )
    if started_after is not None:
        fb_after = pb.add(
            started_after - _TRACE_FALLBACK_WINDOW_SLACK, param_type="DateTime64(6)"
        )
        fallback_conds.append(f"started_at >= {fb_after}")
        base_after = pb.add(started_after, param_type="DateTime64(6)")
        base_conds.append(f"s0.started_at >= {base_after}")
    if started_before is not None:
        fb_before = pb.add(
            started_before + _TRACE_FALLBACK_WINDOW_SLACK, param_type="DateTime64(6)"
        )
        fallback_conds.append(f"started_at < {fb_before}")
        base_before = pb.add(started_before, param_type="DateTime64(6)")
        base_conds.append(f"s0.started_at < {base_before}")

    # The agent triple is inherited together from one span: the span's own
    # immediate parent if it declares an identity, else the earliest
    # identity-declaring span in the trace; conversation_id is inherited on its
    # own. Picking each agent column independently could mix two agents.
    agent_tuple = ", ".join(_AGENT_IDENTITY_COLUMNS)
    agent_tuple_type = ", ".join("String" for _ in _AGENT_IDENTITY_COLUMNS)
    fallback_selects = (
        f"argMinIf(({agent_tuple}), started_at, {_AGENT_IDENTITY_MARKER} != '')\n"
        "            AS fb_agent_identity,\n"
        "          anyIf(conversation_id, conversation_id != '') AS fb_conversation_id,\n"
        f"          CAST(groupArrayIf((span_id, ({agent_tuple})), {_AGENT_IDENTITY_MARKER} != ''),"
        f" 'Map(String, Tuple({agent_tuple_type}))') AS fb_span_agents"
    )
    # Whether the span declares its own agent, computed from the raw column so
    # the coalesce gates below read it instead of the rewritten `agent_name`
    # output alias (ClickHouse resolves a bare column name to a same-name
    # SELECT alias — gating on `agent_name` itself would see the *attributed*
    # value and leak one column of a different agent onto this span).
    own_marker = "has_own_agent_identity"
    parent_marker = "has_parent_agent_identity"
    middle_refs = (
        f"(s0.{_AGENT_IDENTITY_MARKER} != '') AS {own_marker},"
        " tf.fb_agent_identity, tf.fb_conversation_id,"
        " tf.fb_span_agents[s0.parent_span_id] AS parent_agent_identity,"
        f" (parent_agent_identity.1 != '') AS {parent_marker}"
    )
    except_cols = ", ".join(
        [
            *IDENTITY_COLUMNS,
            own_marker,
            parent_marker,
            "fb_agent_identity",
            "fb_conversation_id",
            "parent_agent_identity",
        ]
    )
    # A span keeps its entire own triple if set; else its immediate parent's
    # entire triple if the parent declares one; else the trace-wide fallback.
    # Never a mix of two agents' columns.
    agent_coalesced = ",\n    ".join(
        f"multiIf({own_marker}, {col}, {parent_marker}, parent_agent_identity.{idx},"
        f" fb_agent_identity.{idx}) AS {col}"
        for idx, col in enumerate(_AGENT_IDENTITY_COLUMNS, start=1)
    )
    coalesced = (
        f"{agent_coalesced},\n"
        "    if(conversation_id != '', conversation_id, fb_conversation_id)"
        " AS conversation_id"
    )

    return f"""(
  SELECT * EXCEPT ({except_cols}),
    {coalesced}
  FROM (
    SELECT s0.*, {middle_refs}
    FROM {base_relation} s0
    LEFT JOIN (
      SELECT
          trace_id,
          {fallback_selects}
      FROM spans
      WHERE {" AND ".join(fallback_conds)}
      GROUP BY trace_id
    ) tf ON s0.trace_id = tf.trace_id
    WHERE {" AND ".join(base_conds)}
  )
)"""
