from . import api as weave
from . import context_state

_loading_builtins_token = context_state.set_loading_built_ins()


@weave.op(name="int_concat")
def int_concat(a: int, b: int) -> str:
    return str(a) + str(b)


context_state.clear_loading_built_ins(_loading_builtins_token)


def test_op_def_to_dict():
    assert int_concat.to_dict() == {
        "name": "int_concat",
        "input_types": {"a": "int", "b": "int"},
        "output_type": "string",
    }
