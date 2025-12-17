"""ClickHouse-based project version resolution."""

import logging

import ddtrace
from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ProjectDataResidence

logger = logging.getLogger(__name__)


@ddtrace.tracer.wrap(name="clickhouse_project_version.get_project_data_residence")
def get_project_data_residence(
    project_id: str, ch_client: CHClient
) -> ProjectDataResidence:
    """Determine where project data resides.

    Args:
        project_id: The project identifier.
        ch_client: ClickHouse client.

    Returns:
        ProjectDataResidence enum indicating data presence.
    """
    pb = ParamBuilder()
    project_param = pb.add_param(project_id)
    project_slot = param_slot(project_param, "String")

    # Check both tables in a single query
    query = f"""
        SELECT
            (SELECT 1 FROM calls_complete WHERE project_id = {project_slot} LIMIT 1) as has_complete,
            (SELECT 1 FROM calls_merged WHERE project_id = {project_slot} LIMIT 1) as has_merged
    """

    result = ch_client.query(query, parameters=pb.get_params())

    if result.result_rows:
        row = result.result_rows[0]
        has_complete = row[0]
        has_merged = row[1]

        root_span = ddtrace.tracer.current_root_span()
        if root_span:
            root_span.set_tags({"has_complete": has_complete, "has_merged": has_merged})

        if has_complete and has_merged:
            return ProjectDataResidence.BOTH
        if has_complete:
            return ProjectDataResidence.COMPLETE_ONLY
        if has_merged:
            return ProjectDataResidence.MERGED_ONLY

    return ProjectDataResidence.EMPTY
