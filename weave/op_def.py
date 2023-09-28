import collections
import copy
import contextvars
import contextlib
import typing
import inspect

from weave.weavejs_fixes import fixup_node

from . import errors
from . import op_args
from . import context_state
from . import weave_types as types
from . import uris
from . import graph
from . import weave_internal
from . import pyfunc_type_util
from . import engine_trace
from . import memo
from . import weavify

from .language_features.tagging import (
    opdef_util,
    process_opdef_resolve_fn,
    process_opdef_output_type,
    tagged_value_type,
)
from . import language_autocall


_no_refine: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_no_refine", default=False
)


def refine_enabled() -> bool:
    return not _no_refine.get()


@contextlib.contextmanager
def no_refine():
    token = _no_refine.set(True)
    try:
        yield
    finally:
        _no_refine.reset(token)


def common_name(name: str) -> str:
    return name.split("-")[-1]


# TODO: Move to weave_types after moving TaggedValueType into weave_types
def map_type(
    t: types.Type, map_fn: typing.Callable[[types.Type], types.Type]
) -> types.Type:
    if isinstance(t, types.NoneType):
        pass
    elif isinstance(t, types.Const):
        t = types.Const(map_type(t.val_type, map_fn), t.val)
    elif isinstance(t, types.UnionType):
        t = types.union(*(map_type(m, map_fn) for m in t.members))
    elif isinstance(t, types.TypedDict):
        t = types.TypedDict(
            {k: map_type(v, map_fn) for k, v in t.property_types.items()}
        )
    elif isinstance(t, tagged_value_type.TaggedValueType):
        mapped_tag = map_type(t.tag, map_fn)
        if not isinstance(mapped_tag, types.TypedDict):
            raise errors.WeaveTypeError(
                f"TaggedValueType tag must be a TypedDict, got {mapped_tag}"
            )
        t = tagged_value_type.TaggedValueType(mapped_tag, map_type(t.value, map_fn))
    elif hasattr(t, "object_type"):
        t = t.__class__(object_type=map_type(t.object_type, map_fn))  # type: ignore
    mapped_t = map_fn(t)
    if mapped_t is None:
        return t
    return mapped_t


@memo.memo
def normalize_type(t: types.Type) -> types.Type:
    # This produces equivalent types, but normalized in the way Weave0 expects.
    def _norm(t):
        # Distribute TaggedValueType over UnionType
        if isinstance(t, tagged_value_type.TaggedValueType) and isinstance(
            t.value, types.UnionType
        ):
            return types.union(
                *[
                    tagged_value_type.TaggedValueType(t.tag, m)
                    for m in t.value.members
                    if not isinstance(m, types.NoneType)
                ]
            )

    return map_type(t, _norm)


def _full_output_type(
    params: dict[str, types.Type],
    op_input0_type: types.Type,
    op_output_type: typing.Union[
        types.Type, typing.Callable[[typing.Dict[str, types.Type]], types.Type]
    ],
    param0_is_const: bool,
    param0_const_val: typing.Any,
) -> types.Type:
    # TODO: I think this would be a lot more clear using a stack, since its tail recursive
    # and we have to pass down const information.

    param0_name = list(params.keys())[0]
    param0_type = params[param0_name]
    # Note isinstance check, won't work if op for some reason handles a union of TaggedValueTypes.
    # But the only ops that handle TaggedValueTypes should be tag getters...
    # TODO: formalize?
    if isinstance(param0_type, types.Const):
        # We remove the Const type, since we're computing the output type which can't be const
        # since its derived.
        return _full_output_type(
            {**params, param0_name: param0_type.val_type},
            op_input0_type,
            op_output_type,
            param0_is_const=True,
            param0_const_val=param0_type.val,
        )
    if not isinstance(op_input0_type, types.Function) and isinstance(
        param0_type, types.Function
    ):
        return _full_output_type(
            {**params, param0_name: param0_type.output_type},
            op_input0_type,
            op_output_type,
            param0_is_const=param0_is_const,
            param0_const_val=param0_const_val,
        )
    elif not isinstance(
        op_input0_type, tagged_value_type.TaggedValueType
    ) and isinstance(param0_type, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueType(
            param0_type.tag,
            _full_output_type(
                {**params, param0_name: param0_type.value},
                op_input0_type,
                op_output_type,
                param0_is_const=param0_is_const,
                param0_const_val=param0_const_val,
            ),
        )
    elif isinstance(param0_type, types.UnionType):
        return types.union(
            *(
                _full_output_type(
                    {**params, param0_name: m},
                    op_input0_type,
                    op_output_type,
                    param0_is_const=param0_is_const,
                    param0_const_val=param0_const_val,
                )
                for m in param0_type.members
            )
        )
    elif not op_input0_type.assign_type(types.NoneType()) and isinstance(
        param0_type, types.NoneType
    ):
        return types.NoneType()

    if callable(op_output_type):
        if param0_is_const:
            return op_output_type(
                {**params, param0_name: types.Const(param0_type, param0_const_val)}
            )
        return op_output_type(params)
    return op_output_type


def full_output_type(
    params: dict[str, types.Type],
    op_input0_type: types.Type,
    op_output_type: typing.Union[
        types.Type, typing.Callable[[typing.Dict[str, types.Type]], types.Type]
    ],
) -> types.Type:
    return _full_output_type(params, op_input0_type, op_output_type, False, None)


class OpDef:
    """An Op Definition.

    Must be immediately passed to Register.register_op() after construction.
    """

    input_type: op_args.OpArgs
    raw_output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ]
    refine_output_type: typing.Optional["OpDef"]
    setter: typing.Optional[typing.Callable] = None
    version: typing.Optional[str]
    location: typing.Optional[uris.WeaveURI]
    is_builtin: bool = False
    weave_fn: typing.Optional[graph.Node]
    _decl_locals: typing.Dict[str, typing.Any]
    instance: typing.Union[None, graph.Node]
    hidden: bool
    pure: bool
    mutation: bool
    raw_resolve_fn: typing.Callable
    _output_type: typing.Optional[
        typing.Union[
            types.Type,
            typing.Callable[[typing.Dict[str, types.Type]], types.Type],
        ]
    ]
    plugins: typing.Optional[typing.Dict[str, typing.Any]]

    # This is required to be able to determine which ops were derived from this
    # op. Particularly in cases where we need to rename or lookup when
    # versioned, we cannot rely just on naming structure alone.
    derived_ops: typing.Dict[str, "OpDef"]
    derived_from: typing.Optional["OpDef"]

    # Only used by Tag Getter Ops
    # TODO: How should we support additional info
    # in OpDefs? Maybe we should convert to using plugins
    # like th GQL ops?
    _gets_tag_by_name: typing.Optional[str] = None

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
        hidden=False,
        render_info=None,
        pure=True,
        mutation=False,
        is_builtin: typing.Optional[bool] = None,
        weave_fn: typing.Optional[graph.Node] = None,
        *,
        plugins=None,
        _decl_locals=None,  # These are python locals() from the enclosing scope.
    ):
        self.name = name
        self.input_type = input_type
        self.raw_output_type = output_type
        self.refine_output_type = refine_output_type
        self.raw_resolve_fn = resolve_fn  # type: ignore
        self.setter = setter
        self.render_info = render_info
        self.hidden = hidden
        self.pure = pure
        self.mutation = mutation
        self.is_builtin = (
            is_builtin
            if is_builtin is not None
            else context_state.get_loading_built_ins()
        )
        self._decl_locals = _decl_locals
        self.version = None
        self.location = None
        self.instance = None
        self.derived_ops = {}
        self.derived_from = None
        self.weave_fn = weave_fn
        self._output_type = None
        self.plugins = plugins

    def __get__(self, instance, owner):
        return BoundOpDef(instance, self)

    def __call__(_self, *args, **kwargs):
        # Uses _self instead of self, because self is a typical op argument!
        if _self.mutation:
            # This is hacky. We call the resolver directly, and don't
            # convert arguments to Const nodes. There is no type checking.
            # May need to fix this, but the patterns in test_mutation2 work
            # now.
            from . import object_context

            with object_context.object_context():
                return _self.resolve_fn(*args, **kwargs)
        if context_state.eager_mode():
            return _self.eager_call(*args, **kwargs)
        else:
            return _self.lazy_call(*args, **kwargs)

    def unrefined_output_type_for_params(self, params: typing.Dict[str, graph.Node]):
        if not callable(self.output_type):
            return self.output_type
        new_input_type: dict[str, types.Type] = {}
        for k, n in params.items():
            if isinstance(n, graph.ConstNode) and not isinstance(n.type, types.Const):
                new_input_type[k] = types.Const(n.type, n.val)
            else:
                new_input_type[k] = n.type
        new_input_type = language_autocall.update_input_types(
            self.input_type, new_input_type
        )
        return self.output_type(new_input_type)

    def is_gql_root_resolver(self):
        from . import gql_op_plugin

        return self in gql_op_plugin._ROOT_RESOLVERS

    def lazy_call(_self, *args, **kwargs):
        bound_params = _self.bind_params(args, kwargs)
        # Don't try to refine if there are variable nodes, we are building a
        # function in that case!
        final_output_type: types.Type

        # If there are variables in the graph, prior to refining, try to replace them
        # with their values. This is currently only used in Panel construction paths, to
        # allow refinement to happen. We may want to move to a more general
        # Stack/Context for variables like we have in JS, but this works for now.
        def _replace_var_with_val(n):
            if isinstance(n, graph.VarNode) and hasattr(n, "_var_val"):
                return n._var_val
            return None

        refine_params = {k: graph.resolve_vars(n) for k, n in bound_params.items()}

        # Turn this on to debug scenarios where we don't correctly refine during
        # panel construction (will throw an error instead of letting it happen).
        # if refine_enabled():
        #     for arg_name, arg_node in refine_params.items():
        #         graph_vars = graph.expr_vars(arg_node)
        #         if graph_vars:
        #             raise ValueError(
        #                 "arg contained graph vars (%s): %s"
        #                 % (arg_name, [v.name for v in graph_vars])
        #             )

        if (
            refine_enabled()
            and _self.refine_output_type
            and not any(
                graph.expr_vars(arg_node) for arg_node in refine_params.values()
            )
        ):

            called_refine_output_type = _self.refine_output_type(**refine_params)
            tracer = engine_trace.tracer()  # type: ignore
            with tracer.trace("refine.%s" % _self.uri):
                # api's use auto-creates client. TODO: Fix inline import
                from . import api

                final_output_type = api.use(called_refine_output_type)  # type: ignore
            if final_output_type == None:
                # This can happen due to nullability. In that case, accept the output type is null
                final_output_type = types.NoneType()
            # Have to deref if in case a ref came back...
            from . import storage

            final_output_type = storage.deref(final_output_type)

            final_output_type = (
                process_opdef_output_type.process_opdef_refined_output_type(
                    final_output_type, bound_params, _self
                )
            )
        else:
            final_output_type = _self.unrefined_output_type_for_params(bound_params)
        from . import dispatch

        return dispatch.RuntimeOutputNode(final_output_type, _self.uri, bound_params)

    def eager_call(_self, *args, **kwargs):
        if _self.is_async:
            output_node = _self.lazy_call(*args, **kwargs)
            return weave_internal.use(output_node)
        else:
            return _self.resolve_fn(*args, **kwargs)

    def resolve_fn(__self, *args, **kwargs):
        return process_opdef_resolve_fn.process_opdef_resolve_fn(
            __self, __self.raw_resolve_fn, args, kwargs
        )

    @property
    def output_type(
        self,
    ) -> typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ]:
        if self.name in [
            "save_to_ref",
            "op_get_tag_type",
            "op_make_type_tagged",
            "op_make_type_key_tag",
        ]:
            return self.raw_output_type
        else:
            if isinstance(self.input_type, op_args.OpVarArgs):
                return self.raw_output_type
            elif not isinstance(self.input_type, op_args.OpNamedArgs):
                raise errors.WeaveInternalError('unknown input type for op "%s"')
            if not self.input_type.arg_types:
                return self.raw_output_type
            first_input_type = list(self.input_type.arg_types.values())[0]

            def handle(input_type):
                param0_name = list(input_type.keys())[0]
                param0_type = input_type[param0_name]
                input_type = {**input_type, param0_name: normalize_type(param0_type)}

                def auto_tagging_output_type(input_type):
                    if isinstance(self.raw_output_type, types.Type):
                        result_type = self.raw_output_type
                    else:
                        result_type = self.raw_output_type(input_type)
                    if opdef_util.should_tag_op_def_outputs(self):
                        return tagged_value_type.TaggedValueType(
                            types.TypedDict({param0_name: param0_type}), result_type
                        )
                    return result_type

                final = full_output_type(
                    input_type, first_input_type, auto_tagging_output_type
                )

                return final

            return handle

    @property
    def concrete_output_type(self) -> types.Type:
        if callable(self.raw_output_type):
            try:
                return self.raw_output_type(self.input_type.initial_arg_types)
            except AttributeError:
                return types.UnknownType()
        return self.raw_output_type

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
    def uri(self) -> str:
        return str(self.location) if self.location is not None else self.name

    @property
    def simple_name(self):
        return uris.WeaveURI.parse(self.name).name

    @property
    def is_async(self):
        ot = self.concrete_output_type
        return (
            not callable(self.raw_output_type)
            and isinstance(ot, types.Function)
            and isinstance(ot.output_type, types.RunType)
        )

    def to_dict(self):
        output_type = self.raw_output_type
        if callable(output_type):
            # We can't callable output types to JS yet.
            if self.refine_output_type is not None:
                # if we have a callable output type and refine, js can correctly
                # make use of this op. We set our output type to concrete_output_type
                # and rely on refinement to get the correct output type.
                output_type = self.concrete_output_type.to_dict()
            else:
                # no refine and we have a callable output type. This
                # can't be used by js at the moment.
                raise errors.WeaveSerializeError(
                    "op not serializable for weavejs: %s" % self.name
                )

            # TODO: Consider removing the ability for an output_type to
            # be a function - they all must be Types or ConstNodes. Probably
            # this can be done after all the existing ops can safely be converted.
            # Once that change happens, we can do this conversion in the constructor.
            # output_type = callable_output_type_to_dict(
            #     self.input_type, output_type, self.uri
            # )
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
            # To_dict() is used to send the op list to WeaveJS.
            # We should send the full URI, not just the name, but WeaveJS
            # doesn't handle that yet, so for now, send the name.
            "name": graph.op_full_name(self),
            "input_types": input_types,
            "output_type": output_type,
        }
        if self.hidden:
            serialized["hidden"] = True
        if self.render_info is not None:
            serialized["render_info"] = self.render_info
        if self.refine_output_type is not None:
            serialized["refine_output_type_op_name"] = self.refine_output_type.name
        if self.derived_ops and "mapped" in self.derived_ops:
            serialized["mappable"] = True

        return serialized

    def __repr__(self):
        return "<OpDef: %s %s>" % (self.name, self.version)

    def bind_params(
        self, args: list[typing.Any], kwargs: dict[str, typing.Any]
    ) -> collections.OrderedDict[str, graph.Node]:
        sig = pyfunc_type_util.get_signature(self.raw_resolve_fn)
        bound_params = sig.bind(*args, **kwargs)
        bound_params_with_constants = collections.OrderedDict()
        for k, v in bound_params.arguments.items():
            param = sig.parameters[k]
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                for i, sub_v in enumerate(v):
                    if not isinstance(sub_v, graph.Node):
                        sub_v = weave_internal.const(sub_v)
                    bound_params_with_constants[str(i)] = sub_v
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                for sub_k, sub_v in v.items():
                    if not isinstance(sub_v, graph.Node):
                        sub_v = weave_internal.const(sub_v)
                    bound_params_with_constants[sub_k] = sub_v
            else:
                if not isinstance(self.input_type, op_args.OpNamedArgs):
                    raise errors.WeaveDefinitionError(
                        f"Error binding params to {self.uri} - found named params in signature, but op does not have named param args"
                    )
                param_input_type = self.input_type.arg_types[k]
                if callable(param_input_type):
                    already_bound_types = {
                        k: n.type for k, n in bound_params_with_constants.items()
                    }
                    already_bound_types = language_autocall.update_input_types(
                        self.input_type, already_bound_types
                    )
                    param_input_type = param_input_type(already_bound_types)
                if not isinstance(v, graph.Node):
                    if callable(v):
                        if not isinstance(param_input_type, types.Function):
                            raise errors.WeaveInternalError(
                                "callable passed as argument, but type is not Function. Op: %s"
                                % self.uri
                            )

                        # Allow passing in functions with fewer arguments then the op
                        # declares. E.g. for List.map I pass either of these:
                        #    lambda row, index: ...
                        #    lambda row: ...
                        inner_sig = inspect.signature(v)
                        vars = {}
                        for name in list(param_input_type.input_types.keys())[
                            : len(inner_sig.parameters)
                        ]:
                            vars[name] = param_input_type.input_types[name]

                        v = weave_internal.define_fn(vars, v)
                    else:
                        # TODO: should type-check v here.
                        v = weave_internal.make_const_node(
                            types.TypeRegistry.type_of(v), v
                        )
                bound_params_with_constants[k] = v
        return bound_params_with_constants

    def op_def_is_auto_tag_handling_arrow_op(self) -> bool:
        return isinstance(self, AutoTagHandlingArrowOpDef)


class AutoTagHandlingArrowOpDef(OpDef):
    pass


class BoundOpDef(OpDef):
    bind_self: typing.Optional[graph.Node]

    def __init__(self, bind_self: typing.Optional[graph.Node], op_def: OpDef) -> None:
        self.bind_self = bind_self
        self.op_def = op_def

    def __call__(self, *args, **kwargs):
        if self.bind_self is None:
            return self.op_def(*args, **kwargs)
        else:
            return self.op_def(self.bind_self, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.op_def, name)


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
                {
                    k: types.TypeRegistry.type_of(t)
                    for k, t in input_type.arg_types.items()
                }
            )
        }
        return fixup_node(weave_internal.define_fn(arg_types, output_type)).to_json()
    except errors.WeaveMakeFunctionError as e:
        # print(f"Failed to transform op {op_name}: Invalid output type function")
        return types.Any().to_dict()
