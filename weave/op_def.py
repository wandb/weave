import collections
import copy
from enum import Enum
import inspect
import typing

from weave.weavejs_fixes import fixup_node

from . import errors
from . import op_args
from . import context_state
from . import weave_types as types
from . import uris
from . import graph
from . import weave_internal
from . import pyfunc_type_util


def common_name(name: str) -> str:
    return name.split("-")[-1]


class OpDef:
    """An Op Definition.

    Must be immediately passed to Register.register_op() after construction.
    """

    input_type: op_args.OpArgs
    output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ]
    refine_output_type: typing.Optional["OpDef"]
    setter = str
    call_fn: typing.Any
    version: typing.Optional[str]
    location: typing.Optional[uris.WeaveURI]
    is_builtin: bool = False
    instance: typing.Union[None, graph.Node]

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
        resolve_fn,
        refine_output_type: typing.Optional["OpDef"] = None,
        setter=None,
        render_info=None,
        pure=True,
        is_builtin: typing.Optional[bool] = None,
    ):
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.refine_output_type = refine_output_type
        self._resolve_fn = resolve_fn
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

    def __repr__(self):
        return "<OpDef(%s) %s>" % (id(self), self.name)

    def resolve_fn(__self, *args, **kwargs):
        # TODO: this is a temp hack...it only knows how to pass along the arg tag
        candidate_arg = None
        if len(args) > 0:
            candidate_arg = args[0]
        elif len(kwargs) > 0:
            candidate_arg = list(kwargs.values())[0]
        tags = None
        if isinstance(candidate_arg, types.TaggedValue):
            tags = candidate_arg._tag

        res = __self._resolve_fn(*args, **kwargs)

        named_args = __self.input_type.named_args()
        if (
            tags is not None
            and len(named_args) > 0
            and not types.TaggedType(types.TypedDict({}), types.Any()).assign_type(
                candidate_arg
            )
        ):
            res = types.TaggedValue(tags, res)

        return res

    def __get__(self, instance, owner):
        # This is part of Python's descriptor protocol, and when this op_def
        # is fetched as a member of a class
        self.instance = instance
        return self

    def __call__(_self, *args, **kwargs):
        if _self.instance is not None:
            return _self.call_fn(_self.instance, *args, **kwargs)
        return _self.call_fn(*args, **kwargs)

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
        return getattr(self._resolve_fn, "is_mutation", False)

    @property
    def is_async(self):
        return not callable(self.output_type) and self.output_type.name == "Run"

    def to_dict(self):
        output_type = self.output_type
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
            pyfunc_type_util.get_signature(self._resolve_fn),
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
