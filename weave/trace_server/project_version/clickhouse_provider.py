"""ClickHouse-based project version fallback provider."""

from typing import Any

from weave.trace_server.calls_query_builder.utils import param_slot
from weave.trace_server.orm import ParamBuilder


class ClickHouseProjectVersionProvider:
    """Determines project version by checking for calls_complete table rows.

    Args:
        ch_client: ClickHouse client for querying.

    Examples:
        >>> ch_provider = ClickHouseProjectVersionProvider(ch_client=clickhouse_client)
        >>> version = await ch_provider.get_project_version("proj-123")
    """

    def __init__(self, ch_client: Any):
        self._ch = ch_client

    async def get_project_version(self, project_id: str) -> int:
        """Return 1 if calls_complete has rows, else 0."""
        pb = ParamBuilder()
        project_param = pb.add_param(project_id)
        query = f"""
            SELECT 1
            FROM calls_complete
            WHERE project_id = {param_slot(project_param, "String")}
            LIMIT 1
        """
        try:
            result = self._ch.query(query, parameters=pb.get_params())
        except Exception:
            return 0
        else:
            return 1 if result.result_rows else 0
