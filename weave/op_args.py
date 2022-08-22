import typing
from . import weave_types as types


class OpArgs:
    NAMED_ARGS = "NAMED_ARGS"
    VAR_ARGS = "VAR_ARGS"

    def to_dict(self) -> typing.Union[str, typing.Dict]:
        raise NotImplementedError()

    def weave_type(self) -> types.Type:
        raise NotImplementedError

    @staticmethod
    def from_dict(_type: typing.Union[str, typing.Dict]):
        if isinstance(_type, typing.Dict):
            return OpNamedArgs(
                {
                    key: types.TypeRegistry.type_from_dict(val)
                    for key, val in _type.items()
                }
            )
        else:
            return OpVarArgs(types.TypeRegistry.type_from_dict(_type))


class OpVarArgs(OpArgs):
    kind = OpArgs.VAR_ARGS

    def __init__(self, arg_type: types.Type):
        self.arg_type = arg_type

    def weave_type(self) -> types.Type:
        return types.Dict(types.String(), self.arg_type)

    def to_dict(self) -> str:
        return self.arg_type.to_dict()


class OpNamedArgs(OpArgs):
    kind = OpArgs.NAMED_ARGS

    def __init__(self, arg_types: typing.Dict[str, types.Type]):
        self.arg_types = arg_types

    def weave_type(self) -> types.Type:
        return types.TypedDict(self.arg_types)

    def to_dict(self) -> typing.Dict:
        return {key: val.to_dict() for key, val in self.arg_types.items()}

    def __repr__(self):
        return "<OpNamedArgs %s>" % self.arg_types
