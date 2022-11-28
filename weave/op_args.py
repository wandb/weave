from dataclasses import dataclass
import typing
from . import weave_types as types

BT = typing.TypeVar("BT")


class OpArgs:
    NAMED_ARGS = "NAMED_ARGS"
    VAR_ARGS = "VAR_ARGS"

    def to_dict(self) -> typing.Union[str, typing.Dict]:
        raise NotImplementedError()

    def weave_type(self) -> types.Type:
        raise NotImplementedError()

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

    def params_are_valid(_self, param_types: dict[str, types.Type]) -> bool:
        """Attempts to assign the given param types to the op args. Returns the
        dictionary of assignment results"""
        raise NotImplementedError()

    def named_args(self) -> typing.List["NamedArg"]:
        """Retuns any named arguyments as a list"""
        raise NotImplementedError()

    def create_param_dict(self, args: list[BT], kwargs: dict[str, BT]) -> dict[str, BT]:
        """This is a key function: given a user provided list of args and kwargs, we map them
        to the current paramters and return a paramter dict that can be used by other functions."""
        raise NotImplementedError()


class OpVarArgs(OpArgs):
    kind = OpArgs.VAR_ARGS

    def __init__(self, arg_type: types.Type):
        self.arg_type = arg_type

    def weave_type(self) -> types.Type:
        return types.Dict(types.String(), self.arg_type)

    def to_dict(self) -> typing.Union[str, dict]:
        return self.arg_type.to_dict()

    def params_are_valid(self, param_types: dict[str, types.Type]) -> bool:
        return all(self.arg_type.assign_type(t) for t in param_types.values())

    def named_args(self) -> typing.List["NamedArg"]:
        return []

    def create_param_dict(self, args: list[BT], kwargs: dict[str, BT]) -> dict[str, BT]:
        params = {f"{i}": a for i, a in enumerate(args)}
        params.update(kwargs)
        return params


class OpNamedArgs(OpArgs):
    kind = OpArgs.NAMED_ARGS

    def __init__(
        self,
        # TODO: Add callable as a type of the value
        arg_types: dict[str, types.Type],
    ):
        self.arg_types = arg_types

    def weave_type(self) -> types.Type:
        arg_types: dict[str, types.Type] = {}
        for key, val in self.arg_types.items():
            if callable(val):
                arg_types[key] = val(arg_types)
            else:
                arg_types[key] = val
        return types.TypedDict(arg_types)

    def to_dict(self) -> dict:
        arg_types: dict[str, types.Type] = {}
        for key, val in self.arg_types.items():
            if callable(val):
                arg_types[key] = val(arg_types)
            else:
                arg_types[key] = val
        return {key: val.to_dict() for key, val in arg_types.items()}

    @property
    def initial_arg_types(self) -> dict[str, types.Type]:
        """Returns argument types with functional types resolved"""
        t: dict[str, types.Type] = {}
        for k, v in self.arg_types.items():
            if callable(v):
                t[k] = v(t)
            else:
                t[k] = v
        return t

    def params_are_valid(self, param_dict: dict[str, types.Type]) -> bool:
        valid_params: dict[str, types.Type] = {}
        for k, t in self.arg_types.items():
            if k not in param_dict:
                return False
            if callable(t):
                t = t(valid_params)
            if not t.assign_type(param_dict[k]):
                return False
            valid_params[k] = t
        return True

    def named_args(self) -> typing.List["NamedArg"]:
        return [NamedArg(k, v) for k, v in self.arg_types.items()]

    def create_param_dict(self, args: list[BT], kwargs: dict[str, BT]) -> dict[str, BT]:
        self_keys = list(self.arg_types.keys())
        param_keys = list(kwargs.keys())
        use_name_matching = set(self_keys[len(args) :]) == set(param_keys)
        params: dict[str, BT] = {}
        for i, key in enumerate(self_keys):
            if i < len(args):
                params[key] = args[i]
            else:
                if use_name_matching:
                    params[key] = kwargs[key]
                else:
                    if i - len(args) < len(param_keys):
                        params[key] = kwargs[param_keys[i - len(args)]]
                    else:
                        # TODO: This is the case that we have more args than params
                        # this can happen if we have a default value for an arg. However
                        # this is not tracked currently. After implementing default args
                        # we could throw an error here.
                        pass
        return params

    def __repr__(self):
        return "<OpNamedArgs %s>" % self.arg_types


@dataclass
class NamedArg:
    name: str
    type: types.Type
