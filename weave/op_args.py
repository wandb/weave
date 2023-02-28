from dataclasses import dataclass
import typing
from . import weave_types as types
from . import debug_types

BT = typing.TypeVar("BT")


class OpArgs:
    NAMED_ARGS = "NAMED_ARGS"
    VAR_ARGS = "VAR_ARGS"

    @property
    def initial_arg_types(self) -> dict[str, types.Type]:
        """Returns argument types with functional types resolved"""
        raise NotImplementedError

    def weave_type(self) -> types.Type:
        raise NotImplementedError()

    def to_dict(self) -> dict:
        return {key: val.to_dict() for key, val in self.initial_arg_types.items()}

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

    def first_param_valid(self, param0_type: types.Type) -> bool:
        raise NotImplementedError

    def nonfirst_params_valid(self, param_types: list[types.Type]) -> bool:
        raise NotImplementedError

    def why_are_params_invalid(
        self, param_dict: dict[str, types.Type]
    ) -> typing.Optional[str]:
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

    @property
    def initial_arg_types(self) -> dict[str, types.Type]:
        """Returns argument types with functional types resolved"""
        return {}

    def weave_type(self) -> types.Type:
        return types.Dict(types.String(), self.arg_type)

    def first_param_valid(self, param0_type: types.Type) -> bool:
        return types.optional(self.arg_type).assign_type(param0_type)

    def nonfirst_params_valid(self, param_types: list[types.Type]) -> bool:
        return all(self.arg_type.assign_type(t) for t in param_types)

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
        return types.TypedDict(self.initial_arg_types)

    @property
    def initial_arg_types(self) -> dict[str, types.Type]:
        t: dict[str, types.Type] = {}
        for k, v in self.arg_types.items():
            if callable(v):
                t[k] = v(t)
            else:
                t[k] = v
        return t

    def first_param_valid(self, param0_type: types.Type) -> bool:
        return types.optional(list(self.arg_types.values())[0]).assign_type(param0_type)

    def nonfirst_params_valid(self, param_types: list[types.Type]) -> bool:
        arg_names = list(self.arg_types.keys())
        arg_types = list(self.arg_types.values())
        if len(param_types) < len(arg_types) - 1:
            return False
        valid_params: dict[str, types.Type] = {arg_names[0]: arg_types[0]}
        for at_key, at, pt in zip(arg_names[1:], arg_types[1:], param_types):
            if callable(at):
                at = at(valid_params)
            if not at.assign_type(pt):
                return False
            # TODO: I think this should be pt, but prior implementation has
            # as at.
            valid_params[at_key] = at
        return True

    def why_are_params_invalid(
        self, param_dict: dict[str, types.Type]
    ) -> typing.Optional[str]:
        valid_params: dict[str, types.Type] = {}
        reasons: list[str] = []
        for k, t in self.arg_types.items():
            if k not in param_dict:
                reasons.append(f"Missing parameter {k}")
                continue
            if callable(t):
                t = t(valid_params)
            if not t.assign_type(param_dict[k]):
                reasons.append(
                    f'Parameter "{k}" has invalid type\n{debug_types.why_not_assignable(t, param_dict[k])}'
                )
            valid_params[k] = t
        if reasons:
            return "\n".join(reasons)
        return None

    def named_args(self) -> typing.List["NamedArg"]:
        return [NamedArg(k, v) for k, v in self.arg_types.items()]

    def create_param_dict(self, args: list[BT], kwargs: dict[str, BT]) -> dict[str, BT]:
        # We don't actually use kwarg names!
        self_keys = list(self.arg_types.keys())
        param_keys = list(kwargs.keys())
        params: dict[str, BT] = {}
        for i, key in enumerate(self_keys):
            if i < len(args):
                params[key] = args[i]
            else:
                if i - len(args) < len(param_keys):
                    params[key] = kwargs[param_keys[i - len(args)]]
                else:
                    # This happens during dipatch
                    pass
        return params

    def __repr__(self):
        return "<OpNamedArgs %s>" % self.arg_types


@dataclass
class NamedArg:
    name: str
    type: types.Type
