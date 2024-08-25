import weave
from weave.legacy.weave import ops_arrow


def test_with_columns_basic():
    t = weave.save(
        ops_arrow.to_arrow([{"a": 5, "b": 6, "d": {"y": 9}}, {"a": 7, "d": {"y": 11}}])
    )
    result_node = t.with_columns(
        {
            # should insert entries into d
            "d.x": ops_arrow.to_arrow([1, 2]),
            # should overwrite existing a
            "a": ops_arrow.to_arrow([-1, -2]),
        }
    )
    result = weave.use(result_node)
    assert result_node.type == ops_arrow.ArrowWeaveListType(
        weave.types.TypedDict(
            {
                "b": weave.types.optional(weave.types.Int()),
                "d": weave.types.TypedDict(
                    {"y": weave.types.Int(), "x": weave.types.Int()}
                ),
                "a": weave.types.Int(),
            }
        )
    )
    assert result.to_pylist_tagged() == [
        {"b": 6, "d": {"y": 9, "x": 1}, "a": -1},
        {"b": None, "d": {"y": 11, "x": 2}, "a": -2},
    ]


def test_with_columns_non_dict():
    t = weave.save(
        ops_arrow.to_arrow([{"a": 5, "b": 6, "d": {"y": 9}}, {"a": 7, "d": {"y": 11}}])
    )
    result_node = t.with_columns(
        {
            # a should be replaced with dict
            "a.x": ops_arrow.to_arrow([1, 2]),
        }
    )
    result = weave.use(result_node)
    assert result_node.type == ops_arrow.ArrowWeaveListType(
        weave.types.TypedDict(
            {
                "b": weave.types.optional(weave.types.Int()),
                "d": weave.types.TypedDict({"y": weave.types.Int()}),
                "a": weave.types.TypedDict({"x": weave.types.Int()}),
            }
        )
    )
    assert result.to_pylist_tagged() == [
        {"b": 6, "d": {"y": 9}, "a": {"x": 1}},
        {"b": None, "d": {"y": 11}, "a": {"x": 2}},
    ]


def test_with_columns_length_mismatch():
    t = weave.save(
        ops_arrow.to_arrow([{"a": 5, "b": 6, "d": {"y": 9}}, {"a": 7, "d": {"y": 11}}])
    )
    result = weave.use(t.with_columns({"a": ops_arrow.to_arrow([1])}))
    assert result == None
    result = weave.use(t.with_columns({"a": ops_arrow.to_arrow([1, 2, 3])}))
    assert result == None
