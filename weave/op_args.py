import typing
from . import weave_types as types


class OpArgs:
    NAMED_ARGS = "NAMED_ARGS"
    VAR_ARGS = "VAR_ARGS"


class OpVarArgs(OpArgs):
    kind = OpArgs.VAR_ARGS

    def __init__(self, arg_type: types.Type):
        self.arg_type = arg_type


class OpNamedArgs(OpArgs):
    kind = OpArgs.NAMED_ARGS

    def __init__(self, arg_types: typing.Mapping[str, types.Type]):
        self.arg_types = arg_types
