# from ..ecosystem import keras
import json
import typing
from dataclasses import dataclass

import pytest

from weave.legacy.weave import api as weave
from weave.legacy.weave import context_state

_loading_builtins_token = context_state.set_loading_built_ins()


@dataclass(frozen=True)
class CustomType(weave.types.Type):
    type_var_1: weave.types.Type = weave.types.Any()
    type_var_2: weave.types.Type = weave.types.Any()

    @weave.op(output_type=lambda input_types: input_types["self"].type_var_1)
    def get_1(self):
        return self.type_var_1


@weave.op(
    input_type={"obj": CustomType()},
    output_type=lambda input_types: input_types["obj"][input_types["x"].val],
)
def custom_op(obj, x: str):
    if x == "type_var_1":
        return obj.type_var_1
    elif x == "type_var_2":
        return obj.type_var_2
    else:
        return None


@weave.op(name="int_concat")
def int_concat(a: int, b: int) -> str:
    return str(a) + str(b)


@weave.op(output_type=lambda input_types: input_types["obj"])
def identity(obj: typing.Any):
    return obj


@weave.op(
    output_type=lambda input_types: weave.types.List.make(
        {"object_type": input_types["obj"]}
    )
)
def wrap(obj: typing.Any):
    return [obj]


context_state.clear_loading_built_ins(_loading_builtins_token)

test_data = json.load(open("./legacy/tests/test_op_def_data.json"))


def test_op_def_to_dict():
    assert int_concat.to_dict() == test_data["op_defs"]["int_concat"]["def"]


@pytest.mark.skip("callable output type serialization disabled")
def test_identity():
    assert identity.to_dict() == test_data["op_defs"]["op-identity"]["def"]


@pytest.mark.skip("callable output type serialization disabled")
def test_make_list():
    assert wrap.to_dict() == test_data["op_defs"]["op-wrap"]["def"]


@pytest.mark.skip("callable output type serialization disabled")
def test_custom_datatype():
    assert CustomType.get_1.to_dict() == test_data["op_defs"]["op-get_1"]["def"]
    assert custom_op.to_dict() == test_data["op_defs"]["op-custom_op"]["def"]


@pytest.mark.skip("callable output type serialization disabled")
def test_keras_model():
    assert keras.call_string.to_dict() == test_data["op_defs"]["op-call_string"]["def"]
