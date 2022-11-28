"""Functions for determining which op is being called."""
from dataclasses import dataclass
import functools
import typing

from . import language_nullability

from . import errors
from . import weave_types as types
from . import op_def
from . import op_args
from . import registry_mem
from . import weave_internal
from . import graph
from . import errors
from . import op_aliases


class OpAmbiguityError(Exception):
    pass


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
def op_args_is_subtype(lhs: op_args.OpArgs, rhs: op_args.OpArgs) -> bool:
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


def resolve_op_ambiguity(
    fq_op_name: str, candidates: list[op_def.OpDef]
) -> op_def.OpDef:
    def cmp(a: op_def.OpDef, b: op_def.OpDef) -> int:
        b_is_subtype = op_args_is_subtype(a.input_type, b.input_type)
        a_is_subtype = op_args_is_subtype(b.input_type, a.input_type)
        if a_is_subtype and b_is_subtype:
            raise OpAmbiguityError(
                "Ambiguous ops %s, %s. Ops' input types are equivalent"
                % (a.name, b.name)
            )
        if a_is_subtype:
            return -1
        if b_is_subtype:
            return 1
        raise OpAmbiguityError(
            "Ambiguous ops %s, %s. Ops' input types first arguments must be subset in one direction or the other."
            % (a.name, b.name)
        )

    ordered = sorted(candidates, key=functools.cmp_to_key(cmp))
    return ordered[0]


def get_op_for_input_types(
    fq_op_name: str, args: list[types.Type], kwargs: dict[str, types.Type]
) -> typing.Optional[op_def.OpDef]:
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
    candidates: list[op_def.OpDef] = []
    for op in shared_name_ops:
        param_dict = op.input_type.create_param_dict(args, kwargs)
        param_dict = language_nullability.adjust_assignable_param_dict_for_dispatch(
            op, param_dict
        )
        if op.input_type.params_are_valid(param_dict):
            candidates.append(op)
    if len(candidates) > 1:
        # We definitely have overlap in the input types.
        sorted(candidates, key=lambda c: c.name)
        return resolve_op_ambiguity(fq_op_name, candidates)
    if candidates:
        return candidates[0]
    return None


def dispatch_by_name_and_type(
    common_name: str, self: typing.Any, *args: typing.Any, **kwargs: typing.Any
) -> typing.Any:
    arg_types = [self.type] + [
        arg.type if isinstance(arg, graph.Node) else types.TypeRegistry.type_of(arg)
        for arg in args
    ]
    op = get_op_for_input_types(common_name, arg_types, {})
    if op is not None:
        return op(self, *args)
    aliases = op_aliases.get_op_aliases(common_name)
    raise errors.WeaveDispatchError(
        "No implementation of (%s) found for arg types: %s" % (aliases, arg_types)
    )


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
    to_pylist = None
    as_py = None

    def __dir__(self) -> list[str]:
        ops = registry_mem.memory_registry.find_chainable_ops(self.type)
        return [o.common_name for o in ops]

    def __getattr__(self, attr: str) -> typing.Any:
        node_self = typing.cast(graph.Node, self)
        if attr.startswith("__") and attr.endswith("__"):
            return getattr(super(), attr)

        # First, we check if the attribute matches a known op name...
        ops_with_name = registry_mem.memory_registry.find_ops_by_common_name(attr)
        ops_with_name_and_arg = []
        for op in ops_with_name:
            named_args = op.input_type.named_args()
            if len(
                named_args
            ) > 0 and language_nullability.adjust_input_type_for_mixin_dispatch(
                named_args[0].type
            ).assign_type(
                node_self.type
            ):
                ops_with_name_and_arg.append(op)
        if len(ops_with_name_and_arg) > 0:
            # Here we just return the first op, since the op call itself will dispatch to the correct op
            # if needed
            return op_def.BoundOpDef(node_self, ops_with_name_and_arg[0])
        if node_self.type.__class__ == types.Type:
            # We are doing attribute access on a Weave Type. Let them all through
            # for now.
            obj_getattr = registry_mem.memory_registry.get_op("Object-__getattr__")
            return obj_getattr(node_self, attr)
        self_type = node_self.type
        if not isinstance(self_type, types.ObjectType):
            raise errors.WeaveDispatchError(
                'No ops called "%s" are chainable for type "%s"'
                % (attr, node_self.type)
            )
        # Definitely an ObjectType
        if attr in self_type.property_types():
            obj_getattr = registry_mem.memory_registry.get_op("Object-__getattr__")
            return obj_getattr(node_self, attr)
        raise errors.WeaveDispatchError(
            'No ops or attributes called "%s" available on type "%s"'
            % (attr, node_self.type)
        )

    def __call__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__call__", self, *args, **kwargs)

    def __getitem__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__getitem__", self, *args, **kwargs)

    def __len__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__len__", self, *args, **kwargs)

    def __add__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__add__", self, *args, **kwargs)

    def __sub__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__sub__", self, *args, **kwargs)

    def __mul__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__mul__", self, *args, **kwargs)

    def __truediv__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__truediv__", self, *args, **kwargs)

    def __floordiv__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__floordiv__", self, *args, **kwargs)

    def __pow__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__pow__", self, *args, **kwargs)

    def __mod__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__mod__", self, *args, **kwargs)

    def __round__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__round__", self, *args, **kwargs)

    def __ge__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__ge__", self, *args, **kwargs)

    def __gt__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__gt__", self, *args, **kwargs)

    def __le__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__le__", self, *args, **kwargs)

    def __lt__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__lt__", self, *args, **kwargs)

    def __eq__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__eq__", self, *args, **kwargs)

    def __ne__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__ne__", self, *args, **kwargs)

    def __neg__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__neg__", self, *args, **kwargs)

    def __contains__(self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return dispatch_by_name_and_type("__contains__", self, *args, **kwargs)


class RuntimeOutputNode(graph.OutputNode, DispatchMixin):
    pass


class RuntimeVarNode(graph.VarNode, DispatchMixin):
    pass


class RuntimeConstNode(graph.ConstNode, DispatchMixin):
    pass
