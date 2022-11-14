import collections
import copy
from enum import Enum
import inspect
import typing

import weave
from weave.weavejs_fixes import fixup_node

from . import errors
from . import op_args
from . import context_state
from . import weave_types as types
from . import uris
from . import graph
from . import weave_internal
from . import pyfunc_type_util
from .language_features.tagging import process_opdef_resolve_fn


def common_name(name: str) -> str:
    return name.split("-")[-1]


class OpDef:
    """An Op Definition.

    Must be immediately passed to Register.register_op() after construction.
    """

    raw_input_type: op_args.OpArgs
    _input_type: op_args.OpArgs
    refine_output_type: typing.Optional["OpDef"]
    setter = str
    call_fn: typing.Any
    version: typing.Optional[str]
    location: typing.Optional[uris.WeaveURI]
    is_builtin: bool = False
    instance: typing.Union[None, graph.Node]
    weave_fn: typing.Optional[graph.Node]
    pure: bool
    raw_resolve_fn: typing.Callable
    lazy_call: typing.Optional[typing.Callable]
    eager_call: typing.Optional[typing.Callable]
    _output_type: typing.Optional[
        typing.Union[
            types.Type,
            typing.Callable[[typing.Dict[str, types.Type]], types.Type],
        ]
    ]
    # handles_none: bool

    # This is required to be able to determine which ops were derived from this
    # op. Particularly in cases where we need to rename or lookup when
    # versioned, we cannot rely just on naming structure alone.
    derived_ops: typing.Dict[str, "OpDef"]

    def __init__(
        self,
        name: str,
        input_type: op_args.OpArgs,
        output_type: typing.Union[
            types.Type,
            typing.Callable[[typing.Dict[str, types.Type]], types.Type],
        ],
        resolve_fn: typing.Callable,
        refine_output_type: typing.Optional["OpDef"] = None,
        setter=None,
        render_info=None,
        pure=True,
        is_builtin: typing.Optional[bool] = None,
        weave_fn: typing.Optional[graph.Node] = None,
    ):
        self.name = name
        self.raw_input_type = input_type
        self.raw_output_type = output_type
        self.refine_output_type = refine_output_type
        self.raw_resolve_fn = resolve_fn  # type: ignore
        self.setter = setter
        self.render_info = render_info
        self.pure = pure
        self.is_builtin = (
            is_builtin
            if is_builtin is not None
            else context_state.get_loading_built_ins()
        )
        self.version = None
        self.location = None
        self.lazy_call = None
        self.eager_call = None
        self.call_fn = None
        self.instance = None
        self.derived_ops = {}
        self.weave_fn = weave_fn
        self._output_type = None
        self._input_type = None
        # self.handles_none = _input_type_handles_nones(input_type)

    def __repr__(self):
        return "<OpDef(%s) %s>" % (id(self), self.name)

    def __get__(self, instance, owner):
        # This is part of Python's descriptor protocol, and when this op_def
        # is fetched as a member of a class
        self.instance = instance
        return self

    def __call__(_self, *args, **kwargs):
        if _self.instance is not None:
            return _self.call_fn(_self.instance, *args, **kwargs)
        return _self.call_fn(*args, **kwargs)

    def resolve_fn(__self, *args, **kwargs):
        from . import language_nullability
        res = language_nullability.process_op_def_resolve_fn(__self, args, kwargs)
        return process_opdef_resolve_fn.process_opdef_resolve_fn(
            __self, res, args, kwargs
        )

    @property
    def input_type(self)-> op_args.OpArgs:
        from . import language_nullability
        if self._input_type is None:
            self._input_type = language_nullability.process_op_def_input_type(self.raw_input_type, self)
        return self._input_type

    @property
    def output_type(
        self,
    ) -> typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ]:
        if self._output_type is None:
            if self.name in [
                "op_get_tag_type",
                "op_make_type_tagged",
                "op_make_type_key_tag",
            ]:
                self._output_type = self.raw_output_type
            else:
                # This is a circular import: defining an op requires some ops already defined!
                # We should think about how to get rid of this (probably having a special set of
                # built-in ops that are defined before the rest of the system is loaded).
                from .language_features.tagging.process_opdef_output_type import (
                    process_opdef_output_type,
                )
                from . import language_nullability

                ot = self.raw_output_type

                ot = language_nullability.process_opdef_output_type(
                    ot, self
                )

                ot = process_opdef_output_type(
                    ot, self
                )

                self._output_type = ot

        return self._output_type

    @property
    def concrete_output_type(self) -> types.Type:
        if callable(self.output_type):
            if isinstance(self.input_type, op_args.OpVarArgs):
                return self.output_type({})
            elif isinstance(self.input_type, op_args.OpNamedArgs):
                try:
                    return self.output_type(self.input_type.to_dict())
                except AttributeError:
                    return types.UnknownType()
            else:
                raise NotImplementedError("Unknown input type for op %s" % self.name)
        return self.output_type

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        if name.count("-") > 1:
            raise errors.WeaveDefinitionError(
                "Op names must have at most one hyphen. Got: %s" % name
            )
        self._name = name

    @property
    def common_name(self):
        return common_name(self.name)

    @property
    def uri(self):
        return self.location.uri if self.location is not None else self.name

    @property
    def simple_name(self):
        return uris.WeaveURI.parse(self.name).full_name

    @property
    def is_mutation(self):
        return getattr(self.raw_resolve_fn, "is_mutation", False)

    @property
    def is_async(self):
        return (
            not callable(self.raw_output_type)
            and self.concrete_output_type.name == "Run"
        )

    def to_dict(self):
        output_type = self.raw_output_type
        if callable(output_type):
            # TODO: Consider removing the ability for an output_type to
            # be a function - they all must be Types or ConstNodes. Probably
            # this can be done after all the existing ops can safely be converted.
            # Once that change happens, we can do this conversion in the constructor.
            output_type = callable_output_type_to_dict(
                self.input_type, output_type, self.uri
            )
        else:
            output_type = output_type.to_dict()

        # Make callable input_type args into types.Any() for now.
        input_type = self.input_type
        if isinstance(input_type, op_args.OpVarArgs):
            # This is what we do on the frontend.
            input_types = {"manyX": "invalid"}
        else:
            arg_types = copy.copy(input_type.arg_types)
            for arg_name, arg_type in arg_types.items():
                if callable(arg_type):
                    arg_types[arg_name] = types.Any()
            input_types = op_args.OpNamedArgs(arg_types).to_dict()

        serialized = {
            "name": self.uri,
            "input_types": input_types,
            "output_type": output_type,
        }
        if self.render_info is not None:
            serialized["render_info"] = self.render_info
        if self.refine_output_type is not None:
            serialized["refine_output_type_op_name"] = self.refine_output_type.name

        return serialized

    def __str__(self):
        return "<OpDef: %s>" % self.name

    def bind_params(
        self, args: list[typing.Any], kwargs: dict[str, typing.Any]
    ) -> collections.OrderedDict[str, graph.Node]:
        return weave_internal.bind_value_params_as_nodes(
            self.uri,
            pyfunc_type_util.get_signature(self.raw_resolve_fn),
            args,
            kwargs,
            self.input_type,
        )

    def return_type_of_arg_types(
        self, param_types: dict[str, types.Type]
    ) -> types.Type:
        res_args = self.input_type.assign_param_dict(
            self.input_type.create_param_dict([], param_types)
        )
        if not op_args.all_types_valid(res_args):
            return types.Invalid()
        if isinstance(self.output_type, types.Type):
            return self.output_type
        else:
            return self.output_type(res_args)


def is_op_def(obj):
    return isinstance(obj, OpDef)


def callable_output_type_to_dict(input_type, output_type, op_name):
    if not isinstance(input_type, op_args.OpNamedArgs):
        # print(f"Failed to transform op {op_name}: Requires named args")
        return types.Any().to_dict()
    try:
        # TODO: Make this transformation more sophisticated once the type hierarchy is settled
        arg_types = {
            "input_types": types.TypedDict(
                {k: types.Type() for k, _ in input_type.arg_types.items()}
            )
        }
        return fixup_node(weave_internal.define_fn(arg_types, output_type)).to_json()
    except errors.WeaveMakeFunctionError as e:
        # print(f"Failed to transform op {op_name}: Invalid output type function")
        return types.Any().to_dict()
