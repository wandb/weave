"""Trace scopes for span-ID lookups with additional identity filters."""

from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import ParamBuilder


def get_span_lookup_relation(
    pb: ParamBuilder, *, project_id: str, query: tsi_query.Query | None
) -> str | None:
    """Scope attribution only when every matching row must have one span ID."""
    if query is None:
        return None

    span_id = _get_required_span_id(query.expr_)
    if span_id is None:
        return None

    project_slot = pb.add(project_id, param_type="String")
    span_slot = pb.add(span_id, param_type="String")
    relation = (
        f"(SELECT trace_id FROM spans WHERE project_id = {project_slot} "
        f"AND span_id = {span_slot})"
    )

    return relation


def _get_required_span_id(operand: tsi_query.Operand) -> str | None:
    """Return a span-ID equality required by the operand, ignoring OR and NOT branches."""
    if isinstance(operand, tsi_query.AndOperation):
        for child in operand.and_:
            span_id = _get_required_span_id(child)
            if span_id is not None:
                return span_id

        return None

    # An equality beneath OR or NOT need not hold for every matching row.
    if not isinstance(operand, tsi_query.EqOperation):
        return None

    left, right = operand.eq_
    if isinstance(right, tsi_query.GetFieldOperator):
        left, right = right, left

    if not isinstance(left, tsi_query.GetFieldOperator):
        return None

    if left.get_field_ != "span_id":
        return None

    if not isinstance(right, tsi_query.LiteralOperation):
        return None

    if not isinstance(right.literal_, str):
        return None

    return right.literal_
