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
