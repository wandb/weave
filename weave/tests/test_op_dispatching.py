import weave
from .. import context_state as _context
from .. import weave_internal
from .. import graph

_loading_builtins_token = _context.set_loading_built_ins()


@weave.op()
def add_1(x: int) -> int:
    return x + 1


@weave.op(name="string-special_mult")
def mult_string(x: int, y: str) -> str:
    return y * x


@weave.op(name="number-special_mult")
def mult_number(x: int, y: int) -> int:
    return y * x


_context.clear_loading_built_ins(_loading_builtins_token)


def test_chain():
    a = weave.save(1)
    res = add_1(a)
    assert weave.use(res) == 2
    res = a.add_1()
    assert weave.use(res) == 2


def test_dispatch_params():
    x = weave.save(2)
    num = weave.save(3)
    string = weave.save("a")

    assert weave.use(x.special_mult(string)) == "aa"
    assert weave.use(x.special_mult(num)) == 6


# def test_model_type():
#     dummy_model = weave_internal.make_const_node(
#         weave_keras.KerasModel.make_type(
#             [weave_keras.KerasTensorType.from_list([None, 1], weave.types.String())],
#             [weave_keras.KerasTensorType.from_list([None, 1], weave.types.Number())],
#         ),
#         None,
#     )
#     assert dummy_model.call_string("a").type == weave.types.List(weave.types.Number())
#     dummy_model = weave_internal.make_const_node(
#         weave_keras.KerasModel.make_type(
#             [weave_keras.KerasTensorType.from_list([None, 1], weave.types.String())],
#             [weave_keras.KerasTensorType.from_list([None, 1], weave.types.String())],
#         ),
#         None,
#     )
#     assert dummy_model.call_string("a").type == weave.types.List(weave.types.String())


def test_pick_map():
    a = weave.save([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    res = a.pick("a")
    assert weave.use(res) == [1, 3]


def test_json_pick_map():
    res = weave.graph.OutputNode.from_json(
        {
            "nodeType": "output",
            "type": {"type": "list", "objectType": "number"},
            "fromOp": {
                "name": "pick",
                "inputs": {
                    "obj": {
                        "nodeType": "output",
                        "type": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {"a": "number", "b": "number"},
                            },
                        },
                        "fromOp": {
                            "name": "list",
                            "inputs": {
                                "0": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "typedDict",
                                        "propertyTypes": {"a": "number", "b": "number"},
                                    },
                                    "fromOp": {
                                        "name": "dict",
                                        "inputs": {
                                            "a": {
                                                "nodeType": "const",
                                                "type": "number",
                                                "val": 1,
                                            },
                                            "b": {
                                                "nodeType": "const",
                                                "type": "number",
                                                "val": 2,
                                            },
                                        },
                                    },
                                }
                            },
                        },
                    },
                    "key": {"nodeType": "const", "type": "string", "val": "a"},
                },
            },
        }
    )

    assert weave.use(res) == [1]


def test_nested_js_dict_pick():
    assert (
        weave.use(
            graph.OutputNode(
                weave.types.Number(),
                "pick",
                {
                    "obj": graph.OutputNode(
                        weave.types.TypedDict(
                            {
                                "e": weave.types.Number(),
                                "f": weave.types.Number(),
                                "j": weave.types.Number(),
                            }
                        ),
                        "pick",
                        {
                            "obj": graph.ConstNode(
                                weave.types.TypedDict(
                                    {
                                        "a": weave.types.Number(),
                                        "b": weave.types.Number(),
                                        "c": weave.types.TypedDict(
                                            {
                                                "e": weave.types.Number(),
                                                "f": weave.types.Number(),
                                                "j": weave.types.Number(),
                                            }
                                        ),
                                    }
                                ),
                                {"a": 1, "b": 2, "c": {"d": 3, "e": 4, "f": 5}},
                            ),
                            "key": graph.ConstNode(weave.types.String(), "c"),
                        },
                    ),
                    "key": graph.ConstNode(weave.types.String(), "f"),
                },
            )
        )
        == 5
    )
