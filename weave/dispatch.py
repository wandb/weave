"""Functions for determining which op is being called."""
from dataclasses import dataclass
import functools
import logging
import typing
import json

from .language_features.tagging.is_tag_getter import is_tag_getter
from .language_features.tagging.tagged_value_type import TaggedValueType

from . import weave_types as types
from . import op_def
from . import op_args
from . import registry_mem
from . import graph
from . import errors
from . import pyfunc_type_util
from . import util
from . import memo


# I originally wrote this thinking that we could always choose the more specific
# op, defined as the one that's input types are strict subtypes of the other.
# But consider mapped_add(List[number], number) and
# arrow_mapped_add(ArrowList[number], union[number, ArrowList[number]])
# (this is how we've actually defined those currently)
# ArrowList[number] is a subtype of number, but number is a subtype of
# union[number, ArrowList[number]].
# arrow_mapped_add is more specific in the first arg, but less specific in the
# second!
# So for now, we only consider the first argument.
# TODO: Solve. I see three potential solutions
#   1. Make mapped ops automatically handle arrays in their second argument
#   2. Split arrow ops into two ops, for array/scalar in second arg
#   3. Figure out some clever way to resolve the above ambiguity here
def _op_args_is_subtype(lhs: op_args.OpArgs, rhs: op_args.OpArgs) -> bool:
    """Returns true if rhs is subtype of lhs"""
    if isinstance(lhs, op_args.OpNamedArgs) and isinstance(rhs, op_args.OpNamedArgs):
        if len(lhs.arg_types) != len(rhs.arg_types):
            return False
        for self_type, other_type in list(
            zip(lhs.initial_arg_types.values(), rhs.initial_arg_types.values())
        )[:1]:
            if not self_type.assign_type(other_type):
                return False
        return True
    elif isinstance(lhs, op_args.OpNamedArgs) and isinstance(rhs, op_args.OpVarArgs):
        return all(t.assign_type(rhs.arg_type) for t in lhs.initial_arg_types.values())
    elif isinstance(lhs, op_args.OpVarArgs) and isinstance(rhs, op_args.OpNamedArgs):
        return all(lhs.arg_type.assign_type(t) for t in rhs.initial_arg_types.values())
    elif isinstance(lhs, op_args.OpVarArgs) and isinstance(rhs, op_args.OpVarArgs):
        return lhs.arg_type.assign_type(rhs.arg_type)
    else:
        raise errors.WeaveInternalError("unknown op_args types: %s, %s" % (lhs, rhs))


def _nullability_ambiguity_resolution_rule(
    candidates: list[op_def.OpDef], first_arg_type: types.Type
) -> list[op_def.OpDef]:
    # nullability, if the first argument is None or List[None], then any
    # of the candidates can handle it. Choose the first one (choosing the
    # first ensures we choose a tag getter if there is one).
    if first_arg_type and (
        types.NoneType().assign_type(first_arg_type)
        or types.List(types.NoneType()).assign_type(first_arg_type)
    ):
        return [candidates[0]]
    return candidates


def _is_mapped_op(op: op_def.OpDef) -> bool:
    return op.derived_from is not None and op.derived_from.derived_ops["mapped"] == op
    # Leaving this here, we may want to include this condition in the future
    # or isinstance(op, op_def.AutoTagHandlingArrowOpDef)


def _mapped_ambiguity_resolution_rule(
    candidates: list[op_def.OpDef], first_arg_type: types.Type
) -> list[op_def.OpDef]:
    non_mapped_candidates = [
        candidate for candidate in candidates if not _is_mapped_op(candidate)
    ]
    if len(non_mapped_candidates) > 0:
        return non_mapped_candidates
    return candidates


def _tagged_ambiguity_resolution_rule(
    candidates: list[op_def.OpDef], first_arg_type: types.Type
) -> list[op_def.OpDef]:
    non_tagged_candidates = [
        candidate for candidate in candidates if not is_tag_getter(candidate)
    ]
    if len(non_tagged_candidates) > 0:
        return non_tagged_candidates
    return candidates


def _subtype_sorting_ambiguity_resolution_rule_cmp(
    a: op_def.OpDef, b: op_def.OpDef
) -> int:
    # TODO: make this less hacky
    # If we're mapping contains, don't do substring matching
    ambiguous_contains = ["mapped_string-contains", "contains"]
    if a.name in ambiguous_contains and b.name in ambiguous_contains:
        if a.name == "contains":
            return -1
        else:
            return 1
    b_is_subtype = _op_args_is_subtype(a.input_type, b.input_type)
    a_is_subtype = _op_args_is_subtype(b.input_type, a.input_type)
    if a_is_subtype and b_is_subtype:
        raise errors.WeaveDispatchError(
            "Ambiguous ops %s, %s. Ops' input types are equivalent" % (a.name, b.name)
        )
    if a_is_subtype:
        return -1
    if b_is_subtype:
        return 1
    raise errors.WeaveDispatchError(
        "Ambiguous ops %s, %s. Ops' input types first arguments must be subset in one direction or the other."
        % (a.name, b.name)
    )


def _subtype_sorting_ambiguity_resolution_rule(
    candidates: list[op_def.OpDef], first_arg_type: types.Type
) -> list[op_def.OpDef]:
    return sorted(
        candidates,
        key=functools.cmp_to_key(_subtype_sorting_ambiguity_resolution_rule_cmp),
    )


def _apply_ambiguity_rules(
    candidates: list[op_def.OpDef],
    first_arg_type: types.Type,
    rules: list[
        typing.Tuple[
            str, typing.Callable[[list[op_def.OpDef], types.Type], list[op_def.OpDef]]
        ]
    ],
) -> list[op_def.OpDef]:
    for rule_name, rule in rules:
        reduced_candidates = rule(candidates, first_arg_type)
        if len(reduced_candidates) < len(candidates):
            logging.debug(
                f"Dispatch Ambiguity Resolution - {rule_name} Rule reduced set from {len(candidates)} to {len(reduced_candidates)}"
            )
        candidates = reduced_candidates
        if len(candidates) == 1:
            return candidates
    return candidates


def _resolve_op_ambiguity(
    candidates: list[op_def.OpDef], first_arg_type: types.Type
) -> op_def.OpDef:
    if len(candidates) == 1:
        return candidates[0]
    final_candidates = _apply_ambiguity_rules(
        candidates,
        first_arg_type,
        [
            ("If Null Input, Choose First", _nullability_ambiguity_resolution_rule),
            ("Prefer Non-Mapped", _mapped_ambiguity_resolution_rule),
            ("Prefer Non-Tagged", _tagged_ambiguity_resolution_rule),
            (
                "Prefer Sub Type of Super Type",
                _subtype_sorting_ambiguity_resolution_rule,
            ),
        ],
    )

    return final_candidates[0]


def _get_ops_by_name(fq_op_name: str) -> list[op_def.OpDef]:
    """Returns a single op that matches the given name and raw inputs (inputs can be python objects or nodes)"""
    shared_name_ops: list[op_def.OpDef]

    if fq_op_name.startswith("local-artifact://"):
        # If the incoming op is a locally-defined op, then we are just going to look at the derived op space.
        # We don't need to search the whole registry since by definition it is user-defined
        op = registry_mem.memory_registry.get_op(fq_op_name)
        derived_ops = list(op.derived_ops.values())
        shared_name_ops = [op] + derived_ops
    # Else, we lookup all the ops with the same common name
    else:
        shared_name_ops = registry_mem.memory_registry.find_ops_by_common_name(
            op_def.common_name(fq_op_name)
        )
    return shared_name_ops


def _dispatch_first_arg_inner(name: str, first_arg: types.Type) -> list[op_def.OpDef]:
    ops_with_name = _get_ops_by_name(name)
    ops_with_name_and_arg = []
    for op in ops_with_name:
        if op.input_type.first_param_valid(first_arg):
            ops_with_name_and_arg.append(op)

    return ops_with_name_and_arg


@memo.memo
def _dispatch_first_arg_cached(name: str, first_arg: types.Type) -> list[op_def.OpDef]:
    return _dispatch_first_arg_inner(name, first_arg)


def _dispatch_first_arg(name: str, first_arg: types.Type) -> list[op_def.OpDef]:
    # We want to memoize on the first argument, so that when there are many ops
    # hanging off a single node, we don't redo the dispatch for each. If there is
    # a Const in the Type, we can't hash it (this should be uncommon in the first
    # argument)
    # TODO: track stats
    if not isinstance(first_arg, types.Const):
        try:
            return _dispatch_first_arg_cached(name, first_arg)
        except errors.WeaveHashConstTypeError:
            pass
    return _dispatch_first_arg_inner(name, first_arg)


def _dispatch_remaining_args(
    first_arg_ops: list[op_def.OpDef], kwargs: dict[str, types.Type]
) -> list[op_def.OpDef]:
    candidates: list[op_def.OpDef] = []
    for op in first_arg_ops:
        if op.input_type.nonfirst_params_valid(list(kwargs.values())):
            candidates.append(op)
    return candidates


def get_op_for_inputs(name: str, kwargs: dict[str, types.Type]) -> op_def.OpDef:
    if not kwargs:
        # zero argument ops
        ops = _get_ops_by_name(name)
        if not ops:
            err = errors.WeaveDispatchError(
                f'Cannot dispatch op "{name}"; no matching op found'
            )
            util.raise_exception_with_sentry_if_available(err, [name])
        elif len(ops) > 1:
            err = errors.WeaveDispatchError(
                f'Cannot dispatch zero-arg op "{name}"; multiple matching ops found'
            )
            util.raise_exception_with_sentry_if_available(err, [name])
        return ops[0]

    if (
        name.startswith("panel_table")
        or name.startswith("Query")
        or name.startswith("Facet")
        or name.startswith("panel_plot")
    ):
        # The types don't work for TableState for some reason. This is hacked elsewhere..
        # Hack it some more :(
        # TODO: remove.
        ops = _get_ops_by_name(name)

        # Take that type system!
        ops = [
            o
            for o in ops
            if name.split("-")[0].removeprefix("panel_").lower()
            in json.dumps(list(o.input_type.arg_types.values())[0].to_dict()).lower()  # type: ignore
        ]

        return ops[0]

    input_keys = list(kwargs.keys())
    input_types = list(kwargs.values())

    # Dispatch first arg first. This is important for performance for two reasons:
    # 1. We memoize dispatch_first_arg, so we don't do duplicate work in the case
    #    where executing a graph with lots of fanout. This is common in Weave
    #    (e.g. some_list[0], some_list[1], some_list[2], ...)
    # 2. We don't have to check remaining types for ops that don't match the first
    #    type.
    ops = _dispatch_first_arg(name, input_types[0])
    if not ops:
        logging.info('No ops found for "%s" with first arg "%s"', name, input_types[0])
        err = errors.WeaveDispatchError(
            f'Cannot dispatch op "{name}"; no matching op found for first arg type: {input_types[0]}'
        )
        util.raise_exception_with_sentry_if_available(err, [name])

    final_ops = _dispatch_remaining_args(
        ops, dict(zip(input_keys[1:], input_types[1:]))
    )
    if not final_ops:
        err = errors.WeaveDispatchError(
            f'Cannot dispatch op "{name}"; ops {ops} matched first arg type, but no matching ops found for remaining arg types: {input_types[1:]}'
        )
        util.raise_exception_with_sentry_if_available(err, [name])

    return _resolve_op_ambiguity(final_ops, input_types[0])


def _type_of_input_param(v: typing.Any) -> types.Type:
    if isinstance(v, graph.Node):
        # Check if its a Node first, sometimes we mixin a callables with Node!
        if isinstance(v, graph.ConstNode) and not isinstance(v.type, types.Const):
            return types.Const(v.type, v.val)
        return v.type
    elif callable(v):
        input_type = pyfunc_type_util.determine_input_type(v, None, True)
        output_type = pyfunc_type_util.determine_output_type(v, None, True)
        if not isinstance(input_type, op_args.OpNamedArgs):
            raise errors.WeaveInternalError("Function conversion requires named args")
        if callable(output_type):
            raise errors.WeaveInternalError(
                "Function conversion does not support callable output types"
            )
        return types.Function(
            input_type.arg_types,
            output_type,
        )
    else:
        return types.Const(types.TypeRegistry.type_of(v), v)


def _get_self_bound_input_types(
    self_node: graph.Node, *args: list[typing.Any], **kwargs: dict[str, typing.Any]
) -> dict[str, types.Type]:
    input_types = {"self": _type_of_input_param(self_node)}
    input_types.update({str(i): _type_of_input_param(v) for i, v in enumerate(args)})
    input_types.update({k: _type_of_input_param(v) for k, v in kwargs.items()})
    return input_types


@dataclass
class BoundPotentialOpDefs:
    self_node: graph.Node
    potential_ops: list[op_def.OpDef]

    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> "RuntimeOutputNode":
        inputs = _get_self_bound_input_types(self.self_node, *args, **kwargs)
        input_keys = list(inputs.keys())
        input_types = list(inputs.values())
        ops = _dispatch_remaining_args(
            self.potential_ops, dict(zip(input_keys[1:], input_types[1:]))
        )
        if not ops:
            if any(callable(v) for v in args + tuple(kwargs.values())):
                # _dispatch_remaining_args is broken for callable args. They
                # are dispatchable, and this can be fixed! bind_params in op_def
                # does it correctly. "test_dispatch_lambda" tests this case.
                # TODO: add proper fix
                ops = self.potential_ops
            else:
                err = errors.WeaveDispatchError(
                    f'Cannot dispatch choose op from "{self.potential_ops}"; no matching op found'
                )
                util.raise_exception_with_sentry_if_available(
                    err, [str(self.potential_ops)]
                )
        op = _resolve_op_ambiguity(ops, input_types[0])
        params = op.input_type.create_param_dict([self.self_node] + list(args), kwargs)
        return op(**params)


def _dispatch_dunder(
    name: str,
) -> typing.Callable[..., "RuntimeOutputNode"]:
    def dispatch_dunder_inner(
        self_node: graph.Node, *args: typing.Any, **kwargs: typing.Any
    ) -> "RuntimeOutputNode":
        input_types = _get_self_bound_input_types(self_node, *args, **kwargs)
        op = get_op_for_inputs(name, input_types)
        params = op.input_type.create_param_dict([self_node] + list(args), kwargs)
        return op(**params)

    return dispatch_dunder_inner


class DispatchMixin:
    # Little hack, storage._get_ref expects to be able to check whether
    # any object hasattr('_ref') including nodes. Set it here so that
    # our __getattr__ op method doesn't handle that check.
    _ref = None
    # ipython tries to figure out if we have implemented a __getattr__
    # by checking for this attribute. But the weave.op() decorator makes
    # __getattr__ behave oddly, its now a lazy getattr that will always return
    # something. So add the attribute here to tell ipython that yes we do
    # have a __getattr__. This fixes Node._ipython_display()_ not getting fired.
    _ipython_canary_method_should_not_exist_ = None

    # Needed for storage.to_python hacks. Remove after those hacks are fixed.
    # TODO: fix
    to_pylist_notags = None
    as_py = None

    # This populates jupyter auto-complete, but it also really screws up
    # the vscode debugger
    # def __dir__(self) -> list[str]:
    #     ops = registry_mem.memory_registry.find_chainable_ops(self.type)
    #     return [o.common_name for o in ops]

    def __getattr__(self, attr: str) -> typing.Any:
        node_self = typing.cast(graph.Node, self)
        if attr.startswith("__") and attr.endswith("__"):
            return getattr(super(), attr)
        possible_bound_op = self._get_op(attr)
        if possible_bound_op is not None:
            return possible_bound_op
        possible_prop_node = self._get_prop(attr)
        if possible_prop_node is not None:
            return possible_prop_node
        raise errors.WeaveDispatchError(
            'No ops called "%s" available on type "%s"' % (attr, node_self.type)
        )

    # This implementation is not directly inside of __getattr__ so that
    # tests can call it directly in cases where attributes are overrode
    # by the node class (ex. name, type)
    def _get_op(
        self, attr: str
    ) -> typing.Optional[typing.Union[BoundPotentialOpDefs, op_def.BoundOpDef]]:
        node_self = typing.cast(graph.Node, self)
        ops_with_name_and_arg = _dispatch_first_arg(attr, node_self.type)
        if len(ops_with_name_and_arg) > 0:
            if len(ops_with_name_and_arg) == 1:
                # If there's only one candidate, we can just return it.
                return op_def.BoundOpDef(node_self, ops_with_name_and_arg[0])
            else:
                # Otherwise, we need to wait til we know the rest of the args
                # before we can decide which op to use.
                return BoundPotentialOpDefs(node_self, ops_with_name_and_arg)
        return None

    def _get_prop(self, attr: str) -> typing.Optional[graph.OutputNode]:
        node_self = typing.cast(graph.Node, self)
        use_type = types.non_none(node_self.type)
        if isinstance(use_type, TaggedValueType):
            use_type = use_type.value
        if isinstance(use_type, types.Function):
            use_type = use_type.output_type
        if isinstance(use_type, types.ObjectType):
            # Definitely an ObjectType
            if attr in use_type.property_types():
                obj_getattr = registry_mem.memory_registry.get_op("Object-__getattr__")
                return obj_getattr(node_self, attr)
            else:
                raise errors.WeaveDispatchError(
                    'No attributes called "%s" available on Object "%s"'
                    % (attr, node_self.type)
                )
        return None

    __call__ = _dispatch_dunder("__call__")
    __getitem__ = _dispatch_dunder("__getitem__")
    __len__ = _dispatch_dunder("__len__")
    __add__ = _dispatch_dunder("__add__")
    __sub__ = _dispatch_dunder("__sub__")
    __mul__ = _dispatch_dunder("__mul__")
    __truediv__ = _dispatch_dunder("__truediv__")
    __floordiv__ = _dispatch_dunder("__floordiv__")
    __pow__ = _dispatch_dunder("__pow__")
    __mod__ = _dispatch_dunder("__mod__")
    __round__ = _dispatch_dunder("__round__")
    __ge__ = _dispatch_dunder("__ge__")
    __gt__ = _dispatch_dunder("__gt__")
    __le__ = _dispatch_dunder("__le__")
    __lt__ = _dispatch_dunder("__lt__")
    __eq__ = _dispatch_dunder("__eq__")  # type: ignore
    __ne__ = _dispatch_dunder("__ne__")  # type: ignore
    __neg__ = _dispatch_dunder("__neg__")
    __contains__ = _dispatch_dunder("__contains__")


class RuntimeOutputNode(graph.OutputNode, DispatchMixin):
    pass


class RuntimeVarNode(graph.VarNode, DispatchMixin):
    pass


class RuntimeConstNode(graph.ConstNode, DispatchMixin):
    pass
