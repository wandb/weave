import weave


def test_simple_node():
    num = weave.save(5)
    # store a Node in a sub-key
    contains_node = weave.save({"node": num + 3})
    assert weave.use(contains_node["node"] + 9) == 17


def test_callable_output_type():
    typed_dict = weave.save({"a": {"b": 5}})
    contains_node = weave.save({"node": typed_dict["a"]})
    # calling ["b"] should succeed
    called = contains_node["node"]["b"]
    assert called.type == weave.types.Int()
    assert weave.use(called) == 5


def test_callable_input_type():
    list_ = weave.save([{"a": 5}, {"a": 7}])
    contains_node = weave.save({"node": list_.map(lambda r: r["a"])})
    # calling .map should succeed
    called = contains_node["node"].map(lambda r: r + 3)
    assert called.type == weave.types.List(weave.types.Number())
    assert weave.use(called) == [8, 10]
