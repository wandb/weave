import random
from collections.abc import Iterator

import pytest

from tests.trace.util import (
    client_is_sqlite,
)
from weave.trace import vals
from weave.trace.refs import TableRef
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy


def generate_table_data(client: WeaveClient, n_rows: int, n_cols: int):
    # Create a list of IDs and shuffle them to ensure random order
    ids = list(range(n_rows))
    random.shuffle(ids)

    data = [
        {
            "id": i,
            "nested_col": {
                "prop_a": f"value_{chr(97 + (i % 26))}",  # Use letters a-z cyclically
                "prop_b": f"value_{random.randint(0, 100)}",  # Random integer
            },
            **{
                f"col_{j}": f"value_{random.randint(0, 100)}_{chr(97 + (i % 26))}"
                for j in range(n_cols)
            },
        }
        for i in ids
    ]

    res = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                rows=data,
                project_id=client.project_id,
            ),
        )
    )
    digest = res.digest
    row_digests = res.row_digests

    return digest, row_digests, data


class _FakeTableQueryServer:
    def __init__(self, responses: list[tsi.TableQueryRes]) -> None:
        self.responses = responses
        self.requests: list[tsi.TableQueryReq] = []

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        self.requests.append(req)
        return self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]


def test_weave_table_retries_empty_page_when_table_is_known_non_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vals, "REMOTE_ITER_EMPTY_PAGE_RETRY_DELAY_SECONDS", 0)

    empty_response = tsi.TableQueryRes(rows=[])
    row_response = tsi.TableQueryRes(
        rows=[tsi.TableRowSchema(digest="row-1", val={"value": 1}, original_index=0)]
    )

    # Known non-empty table: an empty first page is inconsistent, so retry.
    server = _FakeTableQueryServer([empty_response, row_response])
    table = vals.WeaveTable(
        server=server,
        table_ref=TableRef(
            entity="entity",
            project="project",
            _digest="table-digest",
            _row_digests=["row-1"],
        ),
    )

    rows = list(table.rows)

    assert len(server.requests) == 2
    assert [request.offset for request in server.requests] == [0, 0]
    assert rows[0]["value"] == 1

    # A known length from a prior stats call also proves an empty page is inconsistent.
    server = _FakeTableQueryServer([empty_response, row_response])
    table = vals.WeaveTable(
        server=server,
        table_ref=TableRef(
            entity="entity",
            project="project",
            _digest="table-digest",
            _row_digests=None,
        ),
    )
    table._known_length = 1

    rows = list(table.rows)

    assert len(server.requests) == 2
    assert [request.offset for request in server.requests] == [0, 0]
    assert rows[0]["value"] == 1

    # Repeated empty pages stop at the retry cap and preserve the empty result.
    server = _FakeTableQueryServer([empty_response])
    table = vals.WeaveTable(
        server=server,
        table_ref=TableRef(
            entity="entity",
            project="project",
            _digest="table-digest",
            _row_digests=["row-1"],
        ),
    )

    assert list(table.rows) == []
    assert len(server.requests) == vals.REMOTE_ITER_EMPTY_PAGE_MAX_ATTEMPTS

    # True empty tables, unknown row digests, and filtered-empty queries do not retry.
    no_retry_cases = [
        (
            TableRef(
                entity="entity",
                project="project",
                _digest="empty-table-digest",
                _row_digests=[],
            ),
            None,
        ),
        (
            TableRef(
                entity="entity",
                project="project",
                _digest="unknown-table-digest",
                _row_digests=None,
            ),
            None,
        ),
        (
            TableRef(
                entity="entity",
                project="project",
                _digest="filtered-table-digest",
                _row_digests=["row-1"],
            ),
            tsi.TableRowFilter(row_digests=["missing-row"]),
        ),
    ]
    for table_ref, table_filter in no_retry_cases:
        server = _FakeTableQueryServer([empty_response])
        table = vals.WeaveTable(
            server=server,
            table_ref=table_ref,
            filter=table_filter,
        )

        assert list(table.rows) == []
        assert len(server.requests) == 1


def test_table_query(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
        )
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    assert result_vals == data
    assert result_digests == row_digests
    assert result_indices == list(range(len(data)))


def test_table_query_stream(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)

    res = client.server.table_query_stream(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
        )
    )

    assert isinstance(res, Iterator)
    rows = []
    for r in res:
        rows.append(r)

    result_vals = [r.val for r in rows]
    result_digests = [r.digest for r in rows]
    result_indices = [r.original_index for r in rows]

    assert result_vals == data
    assert result_digests == row_digests
    assert result_indices == list(range(len(data)))


def test_table_query_invalid_digest(client: WeaveClient):
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest="invalid",
        )
    )

    assert res.rows == []


def test_table_query_filter_by_row_digests(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    filtered_digests = row_digests[2:5]
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=filtered_digests),
        )
    )

    result_digests = [r.digest for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    assert len(result_digests) == 3
    assert result_digests == filtered_digests
    assert result_indices == [2, 3, 4]


def test_table_query_invalid_row_digest(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=["invalid"]),
        )
    )

    assert res.rows == []


def test_table_query_limit(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    limit = 5
    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client.project_id, digest=digest, limit=limit)
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    assert len(result_vals) == limit
    assert result_digests == row_digests[:limit]
    assert result_vals == list(data[:limit])
    assert result_indices == list(range(limit))


def test_table_query_offset(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    offset = 3
    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client.project_id, digest=digest, offset=offset)
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    assert len(result_vals) == len(data) - offset
    assert result_digests == row_digests[offset:]
    assert result_vals == list(data[offset:])
    assert result_indices == list(range(offset, len(data)))


def test_table_query_sort_by_column(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            sort_by=[SortBy(field="id", direction="desc")],
        )
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    sorted_data = sorted(data, key=lambda x: x["id"], reverse=True)
    id_to_index = {d["id"]: i for i, d in enumerate(data)}
    expected_indices = [id_to_index[d["id"]] for d in sorted_data]

    assert result_vals == sorted_data
    assert [r.val["id"] for r in res.rows] != [
        d["id"] for d in data
    ]  # Ensure order is different from original (assertion on the test itself)
    assert result_indices == expected_indices


def test_table_query_sort_by_nested_column(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            sort_by=[SortBy(field="nested_col.prop_a", direction="asc")],
        )
    )

    result_vals = [r.val for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    sorted_data = sorted(data, key=lambda x: x["nested_col"]["prop_a"])
    id_to_index = {d["id"]: i for i, d in enumerate(data)}
    expected_indices = [id_to_index[d["id"]] for d in sorted_data]

    assert result_vals == sorted_data
    assert result_indices == expected_indices


def test_table_query_combined(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 20, 5)

    limit = 5
    offset = 2
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            limit=limit,
            offset=offset,
            sort_by=[SortBy(field="id", direction="desc")],
        )
    )

    result_vals = [r.val for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    sorted_data = sorted(data, key=lambda x: x["id"], reverse=True)
    expected_data = sorted_data[offset : offset + limit]
    id_to_index = {d["id"]: i for i, d in enumerate(data)}
    expected_indices = [id_to_index[d["id"]] for d in expected_data]

    assert len(res.rows) == limit
    assert result_vals == expected_data
    assert result_indices == expected_indices


def test_table_query_multiple_sort_criteria(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 20, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            sort_by=[
                SortBy(field="col_0", direction="asc"),
                SortBy(field="id", direction="desc"),
            ],
        )
    )
    result_vals = [r.val for r in res.rows]
    result_indices = [r.original_index for r in res.rows]

    sorted_data = sorted(data, key=lambda x: (x["col_0"], -x["id"]))
    id_to_index = {d["id"]: i for i, d in enumerate(data)}
    expected_indices = [id_to_index[d["id"]] for d in sorted_data]

    assert result_vals == sorted_data
    assert result_indices == expected_indices


def test_table_query_stats(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)

    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[digest],
        )
    )

    assert stats_res.tables[0].count == len(data)


def test_table_query_stats_empty(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 0, 0)

    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[digest],
        )
    )

    assert stats_res.tables[0].count == len(data)


def test_table_query_stats_missing(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)

    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=["missing"],
        )
    )

    assert len(stats_res.tables) == 0


def generate_duplication_simple_table_data(
    client: WeaveClient, n_rows: int, copy_count: int
):
    # Create a list of IDs and shuffle them to ensure random order
    data = [{"val": i} for i in range(n_rows) for _ in range(copy_count)]

    res = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                rows=data,
                project_id=client.project_id,
            ),
        )
    )
    digest = res.digest
    row_digests = res.row_digests

    return {"digest": digest, "row_digests": row_digests, "data": data}


def test_table_query_with_duplicate_row_digests(client: WeaveClient):
    res1 = generate_duplication_simple_table_data(client, 10, 1)
    res2 = generate_duplication_simple_table_data(client, 10, 2)
    res3 = generate_duplication_simple_table_data(client, 10, 3)

    # Test res1 (copy_count=1)
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res1["digest"],
        )
    )
    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[res1["digest"]],
        )
    )
    assert len(res.rows) == stats_res.tables[0].count == 10
    assert [r.original_index for r in res.rows] == list(range(10))

    # Test filtered query for res1
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res1["digest"],
            filter=tsi.TableRowFilter(row_digests=[res1["row_digests"][0]]),
        )
    )
    assert len(res.rows) == 1
    assert [r.original_index for r in res.rows] == [0]

    # Test res2 (copy_count=2)
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res2["digest"],
        )
    )
    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[res2["digest"]],
        )
    )
    assert len(res.rows) == stats_res.tables[0].count == 20
    assert [r.original_index for r in res.rows] == list(range(20))

    # Test filtered query for res2
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res2["digest"],
            filter=tsi.TableRowFilter(row_digests=[res2["row_digests"][0]]),
        )
    )
    assert len(res.rows) == 2
    assert [r.original_index for r in res.rows] == [0, 1]

    # Test res3 (copy_count=3)
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res3["digest"],
        )
    )
    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[res3["digest"]],
        )
    )
    assert len(res.rows) == stats_res.tables[0].count == 30
    assert [r.original_index for r in res.rows] == list(range(30))

    # Test filtered query for res3
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res3["digest"],
            filter=tsi.TableRowFilter(row_digests=[res3["row_digests"][0]]),
        )
    )
    assert len(res.rows) == 3
    assert [r.original_index for r in res.rows] == [0, 1, 2]


def test_duplicate_table_with_identical_rows(client: WeaveClient):
    data = [{"val": i} for i in range(10)]

    res1 = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                rows=data,
                project_id=client.project_id,
            ),
        )
    )

    # now create the same table with the same data
    res2 = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                rows=data,
                project_id=client.project_id,
            ),
        )
    )

    assert len(res1.row_digests) == 10

    # this is the same table!
    assert res1.digest == res2.digest

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res1.digest,
            sort_by=[SortBy(field="val", direction="asc")],
        )
    )

    # this is the same table, so we should get the same number of rows
    assert len(res.rows) == 10
    assert [r.original_index for r in res.rows] == list(range(10))


def test_table_query_stats_with_storage_size(client: WeaveClient):
    if client_is_sqlite(client):
        pytest.skip("SQLite does not support storage size")

    digest, row_digests, data = generate_table_data(client, 10, 10)

    stats_res = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[digest],
            include_storage_size=True,
        )
    )

    assert stats_res.tables[0].count == len(data)
    assert stats_res.tables[0].storage_size_bytes > 0
