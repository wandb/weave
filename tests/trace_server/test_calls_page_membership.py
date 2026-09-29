import datetime
import uuid

import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.calls_query_builder.calls_query_builder import (
    CallsQuery,
    HardCodedFilter,
    ParamBuilder,
)
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.project_version.types import ReadTable


@pytest.mark.parametrize("offset", [0, 1, 4])
def test_page_membership_preserves_ties_and_empty_pages(
    ch_server: ClickHouseTraceServer, offset: int
) -> None:
    """Load only the selected page across tied timestamps and unrelated IDs."""
    project_id = str(uuid.uuid4())
    started_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    rows = [
        [project_id, call_id, started_at + datetime.timedelta(days=days), "op", "{}"]
        for call_id, days in [("z", 2), ("b", 0), ("a", 0), ("c", 1)]
    ]
    rows.append([str(uuid.uuid4()), "a", started_at, "op", '{"other":true}'])
    ch_server.ch_client.insert(
        "calls_complete",
        rows,
        column_names=["project_id", "id", "started_at", "op_name", "inputs_dump"],
    )
    query = CallsQuery(project_id=project_id, read_table=ReadTable.CALLS_COMPLETE)
    query.add_field("id")
    query.add_field("inputs")
    query.set_hardcoded_filter(HardCodedFilter(filter=tsi.CallsFilter(op_names=["op"])))
    query.add_order("started_at", "asc")
    query.add_order("id", "asc")
    query.set_limit(2)
    query.set_offset(offset)
    params = ParamBuilder()
    sql = query.as_sql(params)

    result = ch_server.ch_client.query(sql, parameters=params.get_params())

    assert result.result_rows == [
        (value, "{}") for value in ["a", "b", "c", "z"][offset : offset + 2]
    ]
