import weave
from weave.legacy.weave import ops_arrow


def test_cond_basic():
    assert weave.use(weave.legacy.weave.ops.cond({"a": True}, {"a": 5})) == 5
    assert weave.use(weave.legacy.weave.ops.cond({"a": False}, {"a": 5})) == None
    assert (
        weave.use(weave.legacy.weave.ops.cond({"a": False, "b": True}, {"a": 5, "b": 6})) == 6
    )


def test_cond_mapped_vector():
    conds = weave.save(
        ops_arrow.to_arrow(
            [{"a": True, "b": False}, {"a": False, "b": False}, {"a": False, "b": True}]
        ),
        "conds",
    )
    assert weave.use(conds.cond({"a": 5, "b": 6})).to_pylist_raw() == [5, None, 6]


def test_cond_mapped_vector_arr_value():
    conds = weave.save(
        ops_arrow.to_arrow(
            [{"a": True, "b": False}, {"a": False, "b": False}, {"a": False, "b": True}]
        ),
        "conds",
    )
    assert weave.use(conds.cond({"a": [1, 2], "b": [5, 6]})).to_pylist_raw() == [
        [1, 2],
        None,
        [5, 6],
    ]


def test_cond_vector():
    conds = weave.save(
        ops_arrow.to_arrow(
            [
                {"a": True, "b": False, "val_a": 5, "val_b": 6},
                {"a": False, "b": False, "val_a": 7, "val_b": 8},
                {"a": False, "b": True, "val_a": 9, "val_b": 10},
            ]
        ),
        "conds",
    )
    assert weave.use(
        conds.map(
            lambda row: weave.legacy.weave.ops.cond(
                weave.legacy.weave.ops.dict_(**{"a": row["a"], "b": row["b"]}),
                weave.legacy.weave.ops.dict_(**{"a": row["val_a"], "b": row["val_b"]}),
            )
        )
    ).to_pylist_raw() == [5, None, 10]


def test_cond_vector_arr_value():
    conds = weave.save(
        ops_arrow.to_arrow(
            [
                {"a": True, "b": False, "val_a": [1, 2], "val_b": [3, 4]},
                {"a": False, "b": False, "val_a": [5, 6], "val_b": [7, 8]},
                {"a": False, "b": True, "val_a": [9, 10], "val_b": [11, 12]},
            ]
        ),
        "conds",
    )
    assert weave.use(
        conds.map(
            lambda row: weave.legacy.weave.ops.cond(
                weave.legacy.weave.ops.dict_(**{"a": row["a"], "b": row["b"]}),
                weave.legacy.weave.ops.dict_(**{"a": row["val_a"], "b": row["val_b"]}),
            )
        )
    ).to_pylist_raw() == [[1, 2], None, [11, 12]]


def test_cond_vector_mixed():
    conds = weave.save(
        ops_arrow.to_arrow(
            [
                {"a": True, "b": False, "val_a": 1, "val_b": 4},
                {"a": False, "b": False, "val_a": 2, "val_b": 5},
                {"a": False, "b": True, "val_a": 3, "val_b": 6},
            ]
        ),
        "conds",
    )
    assert weave.use(
        conds.map(
            lambda row: weave.legacy.weave.ops.cond(
                weave.legacy.weave.ops.dict_(**{"a": row["a"], "b": row["b"]}),
                weave.legacy.weave.ops.dict_(**{"a": row["val_a"], "b": 99}),
            )
        )
    ).to_pylist_raw() == [1, None, 99]


def test_cond_vector_mixed_arr_value():
    conds = weave.save(
        ops_arrow.to_arrow(
            [
                {"a": True, "b": False, "val_a": [1, 2], "val_b": [3, 4]},
                {"a": False, "b": False, "val_a": [5, 6], "val_b": [7, 8]},
                {"a": False, "b": True, "val_a": [9, 10], "val_b": [11, 12]},
            ]
        ),
        "conds",
    )
    assert weave.use(
        conds.map(
            lambda row: weave.legacy.weave.ops.cond(
                weave.legacy.weave.ops.dict_(**{"a": row["a"], "b": row["b"]}),
                weave.legacy.weave.ops.dict_(**{"a": row["val_a"], "b": [99, 100]}),
            )
        )
    ).to_pylist_raw() == [[1, 2], None, [99, 100]]
