from . import api as weave
from . import context

context.set_loading_built_ins(True)


@weave.op(name="int_concat")
def int_concat(a: int, b: int) -> str:
    return str(a) + str(b)


context.set_loading_built_ins(False)


def test_op_def_to_dict():
    assert int_concat.to_dict() == {
        "name": "int_concat",
        "input_types": {"a": "int", "b": "int"},
        "output_type": "string",
    }
