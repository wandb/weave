import typing
from typing import Mapping


if typing.TYPE_CHECKING:
    from .op_def import OpDef

def execute_op(op_def: "OpDef", inputs: Mapping[str, typing.Any]):
    res = op_def.resolve_fn(**inputs)

    return res
