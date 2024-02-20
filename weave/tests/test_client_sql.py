import pytest
from clickhouse_connect import get_client

import weave


@pytest.fixture()
def clickhouse():
    client = get_client(host="localhost")

    client.command("DROP TABLE IF EXISTS objects")
    client.command(
        """
    CREATE TABLE objects (
        id String,
        type String,
        val String,
        files Map(String, String),
        art_meta String)
    ENGINE = MergeTree()
    ORDER BY id
    PRIMARY KEY (id)
    """
    )

    client.command("DROP TABLE IF EXISTS calls")
    client.command(
        """
    CREATE TABLE calls (
        id String,
        trace_id String,
        parent_id String NULL,
        op_name String,
        status_code String,
        start_time DateTime,
        end_time DateTime NULL,
        attributes String,
        inputs String,
        outputs String NULL,
        summary String NULL,
        exception String NULL)
    ENGINE = MergeTree()
    ORDER BY id
    PRIMARY KEY (id)
    """
    )


def test_obj(clickhouse):
    client = get_client(host="localhost")
    with weave.sql_client() as client:
        ref = client.save_object({"a": 5}, "my-num", "latest")
        assert ref.get() == {"a": 5}


def test_op(clickhouse):
    client = get_client(host="localhost")

    @weave.op()
    def my_op(a: int) -> int:
        return a + 1

    with weave.sql_client() as client:
        assert my_op(5) == 6

        op_ref = weave.obj_ref(my_op)
        assert client.ref_is_own(op_ref)
        got_op = weave.storage.get(str(op_ref))


def test_dataset(clickhouse):
    from weave.weaveflow import Dataset

    d = Dataset([{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    with weave.sql_client() as client:
        ref = weave.publish(d)
        d2 = weave.storage.get(str(ref))
    assert d2.rows == d2.rows
