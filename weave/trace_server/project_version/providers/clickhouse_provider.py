"""ClickHouse-based project version provider."""

import logging
from typing import Any, Callable

import ddtrace

from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.project_version.types import ProjectVersion

logger = logging.getLogger(__name__)


class ClickHouseProjectVersionProvider:
    """Determines project version by checking calls_complete and calls_merged tables.

    This provider implements the following logic:
    1. Check calls_complete table for rows
    2. If rows found, return CALLS_COMPLETE_VERSION (1)
    3. If no rows, check calls_merged table
    4. If calls_merged has rows, return CALLS_MERGED_VERSION (0)
    5. If neither table has rows, return EMPTY_PROJECT (-1)

    Args:
        ch_client_factory: Callable that returns a ClickHouse client.
            This allows each thread to get its own thread-local client.

    Examples:
        >>> ch_provider = ClickHouseProjectVersionProvider(ch_client_factory=lambda: get_ch_client())
        >>> version = ch_provider.get_project_version_sync("proj-123")
        >>> assert version in (ProjectVersion.CALLS_MERGED_VERSION, ProjectVersion.CALLS_COMPLETE_VERSION, ProjectVersion.EMPTY_PROJECT)
    """

    def __init__(self, ch_client_factory: Callable[[], Any]):
        self._get_ch_client = ch_client_factory

    @ddtrace.tracer.wrap(name="clickhouse_project_version_provider.get_project_version")
    def get_project_version_sync(
        self, project_id: str, is_write: bool = False
    ) -> ProjectVersion:
        """Determine project version by checking both tables.

        Args:
            project_id: The project identifier.
            is_write: Whether this is for a write operation (unused in this provider).

        Returns:
            ProjectVersion.CALLS_COMPLETE_VERSION (1): If calls_complete has rows
            ProjectVersion.CALLS_MERGED_VERSION (0): If calls_merged has rows but calls_complete doesn't
            ProjectVersion.EMPTY_PROJECT (-1): If neither table has rows
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

        # Get a fresh thread-local client for this query
        ch_client = self._get_ch_client()
        result = ch_client.query(query, parameters=pb.get_params())

        if result.result_rows:
            row = result.result_rows[0]
            has_complete = row[0]
            has_merged = row[1]

            root_span = ddtrace.tracer.current_root_span()
            if root_span:
                root_span.set_tags(
                    {"has_complete": has_complete, "has_merged": has_merged}
                )

            if has_complete and has_merged:
                logger.warning(
                    "Project has traces in both calls_complete and calls_merged tables.",
                    extra={"project_id": project_id},
                )

            if has_merged:
                return ProjectVersion.CALLS_MERGED_VERSION
            elif has_complete:
                return ProjectVersion.CALLS_COMPLETE_VERSION

        # No rows in either table - this is a new/empty project
        return ProjectVersion.EMPTY_PROJECT
