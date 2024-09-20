import random

from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi


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

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]

    assert result_vals == data
    assert result_digests == row_digests


def test_table_query_invalid_digest(client: WeaveClient):
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest="invalid",
        )
    )

    assert res.rows == []


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

    result_digests = [r.digest for r in res.rows]

    assert len(result_digests) == 3
    assert result_digests == filtered_digests


def test_table_query_invalid_row_digest(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 10)
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=["invalid"]),
        )
    )

    assert res.rows == []


def test_table_query_limit(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    limit = 5
    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=digest, limit=limit)
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]

    assert len(result_vals) == limit
    assert result_digests == row_digests[:limit]
    assert result_vals == [d for d in data[:limit]]


def test_table_query_offset(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    offset = 3
    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client._project_id(), digest=digest, offset=offset)
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]

    assert len(result_vals) == len(data) - offset
    assert result_digests == row_digests[offset:]
    assert result_vals == [d for d in data[offset:]]


def test_table_query_sort_by_column(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            sort_by=[tsi.SortBy(field="id", direction="desc")],
        )
    )

    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]

    sorted_data = sorted(data, key=lambda x: x["id"], reverse=True)
    assert result_vals == sorted_data
    assert [r.val["id"] for r in res.rows] != [
        d["id"] for d in data
    ]  # Ensure order is different from original (assertion on the test itself)


def test_table_query_sort_by_nested_column(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 10, 5)

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            sort_by=[tsi.SortBy(field="nested_col.prop_a", direction="asc")],
        )
    )

    result_vals = [r.val for r in res.rows]

    sorted_data = sorted(data, key=lambda x: x["nested_col"]["prop_a"])
    assert result_vals == sorted_data

    assert [r.val["id"] for r in res.rows] != [
        d["id"] for d in data
    ]  # Ensure order is different from original (assertion on the test itself)


def test_table_query_combined(client: WeaveClient):
    digest, row_digests, data = generate_table_data(client, 20, 5)

    limit = 5
    offset = 2
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client._project_id(),
            digest=digest,
            limit=limit,
            offset=offset,
            sort_by=[tsi.SortBy(field="id", direction="desc")],
        )
    )
    result_vals = [r.val for r in res.rows]
    result_digests = [r.digest for r in res.rows]

    sorted_data = sorted(data, key=lambda x: x["id"], reverse=True)
    expected_data = sorted_data[offset : offset + limit]

    assert len(res.rows) == limit
    assert result_vals == expected_data


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
    result_vals = [r.val for r in res.rows]

    sorted_data = sorted(data, key=lambda x: (x["col_0"], -x["id"]))
    assert result_vals == sorted_data
    assert [r.val["id"] for r in res.rows] != [
        d["id"] for d in data
    ]  # Ensure order is different from original  (assertion on the test itself)
