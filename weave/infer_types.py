"""
Functions for inferring Weave Types from Python types.
"""

import collections
import types
import typing
import typing_extensions

from . import weave_types
from . import errors
from . import graph


class TypedDictLike:
    __required_keys__: frozenset[str]


def is_typed_dict_like(t: type) -> typing_extensions.TypeGuard[TypedDictLike]:
    return hasattr(t, "__required_keys__")


def simple_python_type_to_type(py_type: type):
    if isinstance(py_type, str):
        raise errors.WeaveTypeError(
            "Cannot yet detect Weave type from forward type references"
        )
    types = weave_types.instance_class_to_potential_type(py_type)
    if not types:
        return weave_types.UnknownType()
    return types[-1]  # last Type is most specific


def python_type_to_type(
    py_type: typing.Union[types.GenericAlias, type]
) -> weave_types.Type:
    if py_type == typing.Any:
        return weave_types.Any()
    elif isinstance(py_type, typing.TypeVar):
        if py_type.__bound__ is None:
            return weave_types.Any()
        else:
            return python_type_to_type(py_type.__bound__)
    elif isinstance(py_type, types.GenericAlias) or isinstance(
        py_type, typing._GenericAlias  # type: ignore
    ):
        if py_type.__origin__ == typing.Literal:
            members = [
                weave_types.Const(weave_types.TypeRegistry.type_of(v), v)
                for v in py_type.__args__
            ]
            return weave_types.union(*members)
        args = [python_type_to_type(a) for a in py_type.__args__]
        if py_type.__origin__ == list or py_type.__origin__ == collections.abc.Sequence:
            return weave_types.List(*args)
        elif py_type.__origin__ == dict:
            # Special case, we return dict instead of TypedDict
            return weave_types.Dict(*args)
        elif py_type.__origin__ == typing.Union:
            return weave_types.UnionType(*args)
        elif py_type.__origin__ == graph.Node:
            return weave_types.Function({}, args[0])
        else:
            weave_type = simple_python_type_to_type(py_type.__origin__)
            if weave_type == weave_types.UnknownType():
                return weave_type
            return weave_type(*args)
    elif is_typed_dict_like(py_type):
        prop_types = {}
        not_required_keys = set()
        for (
            k,
            t,
        ) in py_type.__annotations__.items():
            if isinstance(t, typing.ForwardRef):
                # Its a ForwardRef if we use typing_extensions.TypedDict
                # which we have to when we want to use NotRequired.
                # But it can be immediately evaluated in the cases we
                # use it.
                t = t._evaluate(
                    {"NotRequired": typing_extensions.NotRequired}, None, frozenset()
                )
                if (
                    hasattr(t, "__origin__")
                    and t.__origin__ == typing_extensions.NotRequired
                ):
                    not_required_keys.add(k)
                    t = t.__args__[0]
            prop_types[k] = python_type_to_type(t)
        return weave_types.TypedDict(prop_types, not_required_keys=not_required_keys)
    weave_type = simple_python_type_to_type(py_type)
    if weave_type == weave_types.UnknownType():
        return weave_type
    try:
        return weave_type()
    except TypeError:
        raise errors.WeaveDefinitionError(
            "Can't instantatiate Weave Type %s without arguments. To fix: ensure all fields have defaults."
            % weave_type
        )
