import wandb

import weave


def test_basic_table(fake_wandb):
    table = wandb.Table(data=[[1, 2, 3]], columns=["a", "b", "c"])

    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)

    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()

    raw_data = weave.use(table_rows).to_pylist_notags()
    assert raw_data == [
        {"a": 1, "b": 2, "c": 3},
    ]
