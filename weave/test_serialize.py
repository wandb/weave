from . import weave_types as types
from . import api
from . import ops
from . import serialize


def test_serialize():
    proj = ops.project("shawn", "show-test")
    av = proj.artifact_version("show", "v14")
    file = av.path("obj.table.json")
    table = file.table()
    rows = table.rows()
    filter_fn = api.define_fn(
        {"row": types.TypedDict({})}, lambda row: row["new"] > 100
    )
    filtered = rows.filter(filter_fn)

    ser = serialize.serialize([filtered])
    deser = serialize.deserialize(ser)
    ser2 = serialize.serialize(deser)
    assert ser == ser2
