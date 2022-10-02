import weave


def test_keys_and_difference():
    a_dict = weave.save({"a": 5, "b": 6, "c": 7})
    a_dict_keys = a_dict.keys()
    assert a_dict_keys.type == weave.types.List(
        weave.types.UnionType(
            weave.types.Const(weave.types.String(), "a"),
            weave.types.Const(weave.types.String(), "b"),
            weave.types.Const(weave.types.String(), "c"),
        )
    )
