import random
from collections.abc import Iterator

from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy


def test_table_query_and_stream(client: WeaveClient):
    """table_query and table_query_stream return the same rows, digests, and indices."""
    digest, row_digests, data = generate_table_data(client, 10, 10)

    res = client.server.table_query(
        tsi.TableQueryReq(project_id=client.project_id, digest=digest)
    )
    assert [r.val for r in res.rows] == data
    assert [r.digest for r in res.rows] == row_digests
    assert [r.original_index for r in res.rows] == list(range(len(data)))

    stream = client.server.table_query_stream(
        tsi.TableQueryReq(project_id=client.project_id, digest=digest)
    )
    assert isinstance(stream, Iterator)
    stream_rows = list(stream)
    assert [r.val for r in stream_rows] == data
    assert [r.digest for r in stream_rows] == row_digests
    assert [r.original_index for r in stream_rows] == list(range(len(data)))


def test_table_query_invalid_and_filter(client: WeaveClient):
    """Invalid table/row digests yield no rows; a row_digests filter returns only the
    matching rows with their original indices."""
    invalid = client.server.table_query(
        tsi.TableQueryReq(project_id=client.project_id, digest="invalid")
    )
    assert invalid.rows == []

    digest, row_digests, data = generate_table_data(client, 10, 5)

    filtered_digests = row_digests[2:5]
    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=filtered_digests),
        )
    )
    assert [r.digest for r in res.rows] == filtered_digests
    assert [r.original_index for r in res.rows] == [2, 3, 4]

    invalid_row = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            filter=tsi.TableRowFilter(row_digests=["invalid"]),
        )
    )
    assert invalid_row.rows == []


def test_table_query_limit_offset_combined(client: WeaveClient):
    """limit, offset, and limit+offset+sort compose as expected over the row set."""
    digest, row_digests, data = generate_table_data(client, 10, 5)

    limit = 5
    limited = client.server.table_query(
        tsi.TableQueryReq(project_id=client.project_id, digest=digest, limit=limit)
    )
    assert [r.val for r in limited.rows] == list(data[:limit])
    assert [r.digest for r in limited.rows] == row_digests[:limit]
    assert [r.original_index for r in limited.rows] == list(range(limit))

    offset = 3
    offsetted = client.server.table_query(
        tsi.TableQueryReq(project_id=client.project_id, digest=digest, offset=offset)
    )
    assert [r.val for r in offsetted.rows] == list(data[offset:])
    assert [r.digest for r in offsetted.rows] == row_digests[offset:]
    assert [r.original_index for r in offsetted.rows] == list(range(offset, len(data)))

    big_digest, _, big_data = generate_table_data(client, 20, 5)
    c_limit, c_offset = 5, 2
    combined = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=big_digest,
            limit=c_limit,
            offset=c_offset,
            sort_by=[SortBy(field="id", direction="desc")],
        )
    )
    sorted_data = sorted(big_data, key=lambda x: x["id"], reverse=True)
    expected_data = sorted_data[c_offset : c_offset + c_limit]
    id_to_index = {d["id"]: i for i, d in enumerate(big_data)}
    assert len(combined.rows) == c_limit
    assert [r.val for r in combined.rows] == expected_data
    assert [r.original_index for r in combined.rows] == [
        id_to_index[d["id"]] for d in expected_data
    ]


def test_table_query_sort_variants(client: WeaveClient):
    """Sorting by a column, a nested column, and multiple criteria all reorder rows
    and preserve original indices."""
    digest, _, data = generate_table_data(client, 10, 5)
    id_to_index = {d["id"]: i for i, d in enumerate(data)}

    by_col = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            sort_by=[SortBy(field="id", direction="desc")],
        )
    )
    sorted_data = sorted(data, key=lambda x: x["id"], reverse=True)
    assert [r.val for r in by_col.rows] == sorted_data
    assert [r.val["id"] for r in by_col.rows] != [d["id"] for d in data]
    assert [r.original_index for r in by_col.rows] == [
        id_to_index[d["id"]] for d in sorted_data
    ]

    by_nested = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=digest,
            sort_by=[SortBy(field="nested_col.prop_a", direction="asc")],
        )
    )
    sorted_nested = sorted(data, key=lambda x: x["nested_col"]["prop_a"])
    assert [r.val for r in by_nested.rows] == sorted_nested
    assert [r.original_index for r in by_nested.rows] == [
        id_to_index[d["id"]] for d in sorted_nested
    ]

    multi_digest, _, multi_data = generate_table_data(client, 20, 5)
    multi_index = {d["id"]: i for i, d in enumerate(multi_data)}
    by_multi = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=multi_digest,
            sort_by=[
                SortBy(field="col_0", direction="asc"),
                SortBy(field="id", direction="desc"),
            ],
        )
    )
    sorted_multi = sorted(multi_data, key=lambda x: (x["col_0"], -x["id"]))
    assert [r.val for r in by_multi.rows] == sorted_multi
    assert [r.original_index for r in by_multi.rows] == [
        multi_index[d["id"]] for d in sorted_multi
    ]


def test_table_query_stats_variants(client: WeaveClient):
    """Stats batch reports counts (incl. empty), skips missing digests, optionally
    reports storage size, and the legacy single-digest endpoint reports count=0 for
    a missing digest instead of erroring."""
    digest, _, data = generate_table_data(client, 10, 10)
    stats = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(project_id=client.project_id, digests=[digest])
    )
    assert stats.tables[0].count == len(data)

    empty_digest, _, empty_data = generate_table_data(client, 0, 0)
    empty_stats = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id, digests=[empty_digest]
        )
    )
    assert empty_stats.tables[0].count == len(empty_data)

    missing_stats = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(project_id=client.project_id, digests=["missing"])
    )
    assert len(missing_stats.tables) == 0

    sized_stats = client.server.table_query_stats_batch(
        tsi.TableQueryStatsBatchReq(
            project_id=client.project_id,
            digests=[digest],
            include_storage_size=True,
        )
    )
    assert sized_stats.tables[0].count == len(data)
    assert sized_stats.tables[0].storage_size_bytes > 0

    # Legacy single-digest endpoint must not IndexError on a missing digest.
    legacy = client.server.table_query_stats(
        tsi.TableQueryStatsReq(project_id=client.project_id, digest="missing")
    )
    assert legacy.count == 0


def test_table_query_with_duplicate_row_digests(client: WeaveClient):
    """Tables with duplicated rows return every physical row with distinct original
    indices, and filtering by a duplicated row digest returns all copies."""
    for copy_count in (1, 2, 3):
        res_data = generate_duplication_simple_table_data(client, 10, copy_count)
        total = 10 * copy_count

        full = client.server.table_query(
            tsi.TableQueryReq(
                project_id=client.project_id, digest=res_data["digest"]
            )
        )
        stats = client.server.table_query_stats_batch(
            tsi.TableQueryStatsBatchReq(
                project_id=client.project_id, digests=[res_data["digest"]]
            )
        )
        assert len(full.rows) == stats.tables[0].count == total
        assert [r.original_index for r in full.rows] == list(range(total))

        filtered = client.server.table_query(
            tsi.TableQueryReq(
                project_id=client.project_id,
                digest=res_data["digest"],
                filter=tsi.TableRowFilter(row_digests=[res_data["row_digests"][0]]),
            )
        )
        assert len(filtered.rows) == copy_count
        assert [r.original_index for r in filtered.rows] == list(range(copy_count))


def test_duplicate_table_with_identical_rows(client: WeaveClient):
    """Creating the same table twice is idempotent: identical digest, full row set."""
    data = [{"val": i} for i in range(10)]

    res1 = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(rows=data, project_id=client.project_id)
        )
    )
    res2 = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(rows=data, project_id=client.project_id)
        )
    )
    assert len(res1.row_digests) == 10
    assert res1.digest == res2.digest

    res = client.server.table_query(
        tsi.TableQueryReq(
            project_id=client.project_id,
            digest=res1.digest,
            sort_by=[SortBy(field="val", direction="asc")],
        )
    )
    assert len(res.rows) == 10
    assert [r.original_index for r in res.rows] == list(range(10))


def generate_table_data(client: WeaveClient, n_rows: int, n_cols: int):
    ids = list(range(n_rows))
    random.shuffle(ids)

    data = [
        {
            "id": i,
            "nested_col": {
                "prop_a": f"value_{chr(97 + (i % 26))}",
                "prop_b": f"value_{random.randint(0, 100)}",
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
            table=tsi.TableSchemaForInsert(rows=data, project_id=client.project_id)
        )
    )
    return res.digest, res.row_digests, data


def generate_duplication_simple_table_data(
    client: WeaveClient, n_rows: int, copy_count: int
):
    data = [{"val": i} for i in range(n_rows) for _ in range(copy_count)]
    res = client.server.table_create(
        tsi.TableCreateReq(
            table=tsi.TableSchemaForInsert(rows=data, project_id=client.project_id)
        )
    )
    return {"digest": res.digest, "row_digests": res.row_digests, "data": data}
