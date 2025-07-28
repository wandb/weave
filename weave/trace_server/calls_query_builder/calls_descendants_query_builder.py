from typing import Optional

from weave.trace_server.orm import ParamBuilder
from weave.trace_server.calls_query_builder.utils import param_slot

def make_descendants_query(
    project_id: str,
    parent_call_ids: list[str] | None,
    max_depth: int | None,
    table_alias: str,
    pb: ParamBuilder,
) -> tuple[Optional[str], Optional[str]]:
    if not parent_call_ids:
        return None, None
    
    cte_name = "descendant_call_ids"
    descendant_cte = build_descendant_cte_sql(
        project_id,
        parent_call_ids,
        max_depth,
        cte_name,
        table_alias,
        pb,
    )
    descendant_filter_sql = f"AND ({table_alias}.id IN (SELECT id FROM {cte_name}))"

    return descendant_cte, descendant_filter_sql


def build_descendant_cte_sql(
    project_id: str,
    parent_ids: list[str],
    max_depth: Optional[int],
    cte_name: str,
    table_alias: str,
    pb: ParamBuilder,
) -> str:
    """
    Builds a recursive CTE SQL string for finding descendant calls.

    Args:
        project_id: The project ID to filter by
        parent_ids: List of parent call IDs to find descendants for
        pb: ParamBuilder for parameterization
        max_depth: Optional maximum recursion depth (defaults to 100)

    Returns:
        SQL string for the recursive CTE
    """
    max_depth = max_depth or 100
    max_depth_param = pb.add_param(max_depth)
    project_id_param = pb.add_param(project_id)
    parent_ids_param = pb.add_param(parent_ids)

    # Base case: select the immediate children of parent call IDs
    base_case_sql = f"""
    SELECT id, 1 AS depth
    FROM {table_alias}
    WHERE project_id = {param_slot(project_id_param, "String")}
      AND parent_id IN {param_slot(parent_ids_param, "Array(String)")}
    """

    # Recursive case: select children IDs of previous level
    # Prevent infinite recursion by limiting depth
    recursive_case_sql = f"""
    SELECT c.id, d.depth + 1 AS depth
    FROM {table_alias} c
    INNER JOIN {cte_name} d ON c.parent_id = d.id
    WHERE c.project_id = {param_slot(project_id_param, "String")}
        AND d.depth < {param_slot(max_depth_param, "UInt64")}
    """

    descendant_sql = f"""RECURSIVE {cte_name} AS (
    {base_case_sql}
    UNION ALL
    {recursive_case_sql})
    """

    return descendant_sql
