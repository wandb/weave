import weave
from weave.legacy.weave import weave_internal


def test_weave_fn_in_data():
    weave_fn = weave_internal.define_fn({"x": weave.types.Int()}, lambda x: x + 3)
    data = weave.save({"a": weave_fn})
    assert weave.use(data["a"](5)) == 8


def test_weave_fn_in_data_called_in_callback():
    weave_fn = weave_internal.define_fn({"x": weave.types.Int()}, lambda x: x + 3)
    data = weave.save({"a": weave_fn})
    my_list = weave.save([1, 2, 3])
    assert weave.use(my_list.filter(lambda row: data["a"](row) > 4)) == [2, 3]
