"""ClickHouse-based project version fallback provider."""

from typing import Any

from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ProjectVersion


class ClickHouseProjectVersionProvider:
    """Determines project version by checking calls_complete and calls_merged tables.

    This provider implements the following logic:
    1. Check calls_complete table for rows
    2. If rows found, return NEW_VERSION (1)
    3. If no rows, check calls_merged table
    4. If calls_merged has rows, return OLD_VERSION (0)
    5. If neither table has rows, return EMPTY_PROJECT (-1)

    Args:
        ch_client: ClickHouse client for querying.

    Examples:
        >>> ch_provider = ClickHouseProjectVersionProvider(ch_client=clickhouse_client)
        >>> version = await ch_provider.get_project_version("proj-123")
        >>> assert version in (ProjectVersion.OLD_VERSION, ProjectVersion.NEW_VERSION, ProjectVersion.EMPTY_PROJECT)
    """

    def __init__(self, ch_client: Any):
        self._ch = ch_client

    async def get_project_version(self, project_id: str) -> ProjectVersion:
        """Determine project version by checking both tables.

        Returns:
            ProjectVersion.NEW_VERSION (1): If calls_complete has rows
            ProjectVersion.OLD_VERSION (0): If calls_merged has rows but calls_complete doesn't
            ProjectVersion.EMPTY_PROJECT (-1): If neither table has rows
        """
        pb = ParamBuilder()
        project_param = pb.add_param(project_id)

        # First check calls_complete (new table)
        query_complete = f"""
            SELECT 1
            FROM calls_complete
            WHERE project_id = {param_slot(project_param, "String")}
            LIMIT 1
        """
        try:
            result = self._ch.query(query_complete, parameters=pb.get_params())
            if result.result_rows:
                return ProjectVersion.NEW_VERSION
        except Exception:
            # If calls_complete doesn't exist or query fails, fall through to check calls_merged
            pass

        # No rows in calls_complete, check calls_merged (old table)
        query_merged = f"""
            SELECT 1
            FROM calls_merged
            WHERE project_id = {param_slot(project_param, "String")}
            LIMIT 1
        """
        try:
            result = self._ch.query(query_merged, parameters=pb.get_params())
            if result.result_rows:
                return ProjectVersion.OLD_VERSION
        except Exception:
            # If calls_merged doesn't exist or query fails, treat as empty
            pass

        # No rows in either table - this is a new/empty project
        return ProjectVersion.EMPTY_PROJECT
