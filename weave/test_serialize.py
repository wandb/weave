from . import weave_types as types
from . import api
from . import ops
from . import serialize


def test_serialize(fake_wandb):
    proj = ops.project("shawn", "show-test")
    av = proj.artifact_version("show", "v14")
    file = av.path("test_results.table.json")
    table = file.table()
    rows = table.rows()
    filter_fn = api.define_fn(
        {"row": types.TypedDict({})}, lambda row: row["new"] + 100
    )
    filtered = rows.map(filter_fn)

    ser = serialize.serialize([filtered])
    deser = serialize.deserialize(ser)
    ser2 = serialize.serialize(deser)
    assert ser == ser2


def test_serialize_nested_function():
    rows = api.save([{"a": [1, 2]}])
    filtered = rows.filter(
        api.define_fn(
            {"row": types.TypedDict({"a": types.List(types.Int())})},
            lambda row: ops.numbers_avg(
                row["a"].map(api.define_fn({"row": types.Int()}, lambda row: row + 1))
            ),
        )
    )

    ser = serialize.serialize([filtered])
    deser = serialize.deserialize(ser)
    ser2 = serialize.serialize(deser)
    assert ser == ser2
