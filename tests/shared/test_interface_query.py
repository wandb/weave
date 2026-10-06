import pytest

from weave.shared.interface import query
from weave.trace_server.interface import query as query_legacy

pytestmark = pytest.mark.trace_server


def test_trace_server_query_reexports_the_same_objects() -> None:
    assert query.Query is query_legacy.Query
    assert query.GetFieldOperator is query_legacy.GetFieldOperator
    assert query.LiteralOperation is query_legacy.LiteralOperation
