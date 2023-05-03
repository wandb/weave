import weave


def test_publish_values(user_by_api_key_in_env):
    data = ["a", "b", "c"]
    res = weave.publish(data, "weave_ops/list")
    assert weave.use(res) == data


def test_publish_panel(user_by_api_key_in_env):
    table_obj = weave.panels.Table(
        weave.make_node(
            [
                {"a": 1, "b": 2, "c": 3},
                {"a": 4, "b": 5, "c": 6},
                {"a": 7, "b": 8, "c": 9},
            ]
        ),
        columns=[
            lambda row: row["a"],
            lambda row: row["b"],
            lambda row: row["c"],
        ],
    )
    res = weave.publish(table_obj, "weave_ops/table")
    assert isinstance(res, weave.graph.Node)
