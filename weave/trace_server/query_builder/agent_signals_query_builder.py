"""ClickHouse list/count queries for server-paginated agent Signals."""

from __future__ import annotations

import logging

from weave.trace_server.agents.span_costs import cost_augmented_source_sql
from weave.trace_server.agents.types import AgentSignalsQueryReq
from weave.trace_server.calls_query_builder.utils import param_slot, safely_format_sql
from weave.trace_server.feedback_agg_query_builder import build_feedback_filter_sql
from weave.trace_server.orm import ParamBuilder

logger = logging.getLogger(__name__)

_RATING_KEY = "_rating_"
_SIGNAL_COLUMNS: tuple[str, ...] = (
    "id",
    "project_id",
    "weave_ref",
    "wb_user_id",
    "creator",
    "created_at",
    "feedback_type",
    "runnable_ref",
    "scorer_tags",
    "scorer_tag_reasons",
    "scorer_tag_confidences",
    "scorer_ratings",
    "scorer_rating_reasons",
    "scorer_rating_confidences",
    "span_agent_name",
    "span_conversation_id",
    "span_trace_id",
    "scorer_trace_id",
)


def _where_sql(req: AgentSignalsQueryReq, pb: ParamBuilder) -> str:
    project_param = pb.add_param(req.project_id)
    after_param = pb.add_param(req.after_ms)
    before_param = pb.add_param(req.before_ms)
    filters = build_feedback_filter_sql(
        req, project_param, after_param, before_param, pb
    )
    return f"({filters}) AND (notEmpty(scorer_tags) OR notEmpty(scorer_ratings))"


def make_agent_signals_count_query(pb: ParamBuilder, req: AgentSignalsQueryReq) -> str:
    """Count exactly the signal rows eligible for the requested page."""
    raw_sql = f"SELECT count() FROM feedback WHERE {_where_sql(req, pb)}"
    return safely_format_sql(raw_sql, logger)


def make_agent_signals_list_query(pb: ParamBuilder, req: AgentSignalsQueryReq) -> str:
    """Return one stable page, pricing each scorer trace at query time."""
    rating_key = param_slot(pb.add_param(_RATING_KEY), "String")
    feedback_columns = ",\n          ".join(_SIGNAL_COLUMNS)
    filtered_feedback = f"""
        SELECT
          {feedback_columns},
          if(
            mapContains(scorer_ratings, {rating_key}),
            scorer_ratings[{rating_key}],
            NULL
          ) AS rating
        FROM feedback
        WHERE {_where_sql(req, pb)}
    """

    direction = req.sort_by.direction.upper()
    if req.sort_by.field == "created_at":
        order_sql = f"f.created_at {direction}, f.id {direction}"
    elif req.sort_by.field == "rating":
        order_sql = f"f.rating {direction} NULLS LAST, f.created_at DESC, f.id DESC"
    elif req.sort_by.field == "total_cost_usd":
        order_sql = (
            f"c.total_cost_usd {direction} NULLS LAST, f.created_at DESC, f.id DESC"
        )
    else:
        raise ValueError(f"unsupported Signals sort field: {req.sort_by.field!r}")

    limit_slot = param_slot(pb.add_param(req.limit), "UInt64")
    offset_slot = param_slot(pb.add_param(req.offset), "UInt64")
    cost_sort = req.sort_by.field == "total_cost_usd"
    page_cte = ""
    cost_scope = "filtered_feedback"
    result_relation = "filtered_feedback"
    final_pagination = f"LIMIT {limit_slot}\n    OFFSET {offset_slot}"
    if not cost_sort:
        page_cte = f""",
      page_feedback AS (
        SELECT * FROM filtered_feedback f
        ORDER BY {order_sql}
        LIMIT {limit_slot}
        OFFSET {offset_slot}
      )"""
        cost_scope = "page_feedback"
        result_relation = "page_feedback"
        final_pagination = ""

    project_slot = param_slot(pb.add_param(req.project_id), "String")
    scoped_spans = f"""(
        SELECT *
        FROM spans
        WHERE project_id = {project_slot}
          AND trace_id IN (
            SELECT scorer_trace_id
            FROM {cost_scope}
            WHERE scorer_trace_id != ''
          )
    )"""
    cost_source = cost_augmented_source_sql(
        pb, req.project_id, base_relation=scoped_spans
    )
    scorer_costs = f"""
        SELECT
          s.trace_id,
          sumOrNull(s.total_cost_usd) AS total_cost_usd
        FROM {cost_source} s
        GROUP BY s.trace_id
    """

    output_columns = ",\n      ".join(f"f.{column}" for column in _SIGNAL_COLUMNS)
    raw_sql = f"""
    WITH
      filtered_feedback AS ({filtered_feedback}){page_cte},
      scorer_costs AS ({scorer_costs})
    SELECT
      {output_columns},
      c.total_cost_usd
    FROM {result_relation} f
    LEFT ANY JOIN scorer_costs c ON c.trace_id = f.scorer_trace_id
    ORDER BY {order_sql}
    {final_pagination}
    """
    return safely_format_sql(raw_sql, logger)
