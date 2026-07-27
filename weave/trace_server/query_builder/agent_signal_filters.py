"""SQL helpers for agent signal filters."""

from __future__ import annotations

from weave.trace_server.agents.types import AgentSignalFilter
from weave.trace_server.interface.feedback_types import AGENT_SPAN_FEEDBACK_TYPES
from weave.trace_server.orm import ParamBuilder

_OP_TO_SQL: dict[str, str] = {
    "gte": ">=",
    "gt": ">",
    "lte": "<=",
    "lt": "<",
    "eq": "=",
}

# Derived from the write-path constant so a change to the frozenset propagates here.
# Sorted for a deterministic SQL string; these are trusted literals, not user input.
_AGENT_FEEDBACK_TYPES_SQL = "feedback_type IN ({})".format(
    ", ".join(
        f"'{feedback_type}'" for feedback_type in sorted(AGENT_SPAN_FEEDBACK_TYPES)
    )
)


def build_signal_filter_clause(
    pb: ParamBuilder,
    project_id: str,
    signal_filters: AgentSignalFilter | None,
    conversation_col: str = "s.conversation_id",
) -> str | None:
    """Restrict `conversation_col` to conversations carrying the requested signals.

    Matches conversations with all provided filters across all feedback rows.
    Tags and ratings often live on separate rows, so each requested signal becomes
    its own grouped HAVING term.

    Returns None for an empty filter, so callers omit the semi-join. Not
    time-constrained: a signal's timestamp is not the conversation's.
    """
    if signal_filters is None or signal_filters.is_empty():
        return None

    pid_slot = pb.add(project_id, param_type="String")
    having_terms: list[str] = []

    if signal_filters.tags:
        tags_slot = pb.add(signal_filters.tags, param_type="Array(String)")
        having_terms.append(f"sum(hasAny(scorer_tags, {tags_slot})) > 0")

    for cond in signal_filters.ratings:
        key_slot = pb.add(cond.scorer_key, param_type="String")
        val_slot = pb.add(cond.value, param_type="Float64")
        op = _OP_TO_SQL[cond.op]
        # mapContains guard: Map access returns 0.0 for an absent key, which
        # would spuriously pass a `>= 0` test.
        having_terms.append(
            f"sum(mapContains(scorer_ratings, {key_slot}) "
            f"AND scorer_ratings[{key_slot}] {op} {val_slot}) > 0"
        )

    having = " AND ".join(having_terms)
    return (
        f"{conversation_col} IN (SELECT span_conversation_id FROM feedback "
        f"WHERE project_id = {pid_slot} AND {_AGENT_FEEDBACK_TYPES_SQL} "
        f"AND span_conversation_id != '' "
        f"GROUP BY span_conversation_id HAVING {having})"
    )
