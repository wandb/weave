from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


def generate_table_data(client: WeaveClient, n_rows: int, n_cols: int):
    data = [
        {
            "id": i,
            "nested_col": {
                "prop_a": f"value_{i}_a",
                "prop_b": f"value_{i}_b",
            },
            **{f"col_{j}": f"value_{i}_{j}" for j in range(n_cols)},
        }
        for i in range(n_rows)
    ]

    res = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(
                rows=data,
                project_id=client._project_id(),
            ),
        )
    )
    digest = res.digest
    row_digests = res.row_digests

    return digest, row_digests, data


def test_table_query(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
        )
    )

    row_data = [r.val for r in res.rows]
    row_digests = [r.digest for r in res.rows]

    assert row_data == data
    assert row_digests == row_digests


def test_table_query_filter_by_row_digests(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    filtered_digests = row_digests[2:5]
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=filtered_digests),
        )
    )

    assert len(res.rows) == 3
    assert [r.digest for r in res.rows] == filtered_digests
    assert [r.val for r in res.rows] == data[2:5]


def test_table_query_limit(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    limit = 5
    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=digest, limit=limit)
    )

    assert len(res.rows) == limit
    assert [r.val for r in res.rows] == data[:limit]


def test_table_query_offset(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    offset = 3
    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=digest, offset=offset)
    )

    assert len(res.rows) == len(data) - offset
    assert [r.val for r in res.rows] == data[offset:]


def test_table_query_sort_no_sort(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
        )
    )

    assert [r.val for r in res.rows] == data


def test_table_query_sort_by_column(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            sort_by=[tsi.SortBy(field="id", direction="desc")],
        )
    )

    sorted_data = sorted(data, key=lambda x: x["id"], reverse=True)
    assert [r.val for r in res.rows] == sorted_data


def test_table_query_sort_by_nested_column(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            sort_by=[tsi.SortBy(field="nested_col.prop_a", direction="asc")],
        )
    )

    sorted_data = sorted(data, key=lambda x: x["nested_col"]["prop_a"])
    assert [r.val for r in res.rows] == sorted_data


def test_table_query_combined(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 20, 5)

    filtered_digests = row_digests[5:15]
    limit = 5
    offset = 2
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=filtered_digests),
            limit=limit,
            offset=offset,
            sort_by=[tsi.SortBy(field="id", direction="desc")],
        )
    )

    filtered_data = [d for d in data if d["id"] in range(5, 15)]
    sorted_data = sorted(filtered_data, key=lambda x: x["id"], reverse=True)
    expected_data = sorted_data[offset : offset + limit]

    assert len(res.rows) == limit
    assert [r.val for r in res.rows] == expected_data


def test_table_query_multiple_sort_criteria(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 20, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            sort_by=[
                tsi.SortBy(field="col_0", direction="asc"),
                tsi.SortBy(field="id", direction="desc"),
            ],
        )
    )

    sorted_data = sorted(data, key=lambda x: (x["col_0"], -x["id"]))
    assert [r.val for r in res.rows] == sorted_data
