"""Functions for determining which op is being called."""
from dataclasses import dataclass
import typing

from . import language_nullability

from . import errors
from . import types
from . import op_def
from . import op_args
from . import registry_mem
from . import weave_internal
from . import graph


@dataclass
class Candidate:
    op: op_def.OpDef
    assigned_param_dict: dict[str, types.Type]


def resolve_op_ambiguity(fq_op_name: str, candidates: list[Candidate]) -> op_def.OpDef:
    match = None
    for candidate in candidates:
        if candidate.op.name == fq_op_name:
            match = candidate.op
            break
    if match is not None:
        return match
    # TODO: Implement intelligent disambiguiation via narrowing.
    #
    #
    # Rejecting here is important. We don't in Weave0, which is what leads to ambiguous.
    # cases.
    # TODO: reject earlier, at declaration time.
    raise errors.WeaveInternalError(
        "Too many candidate ops, this means there are two ops declared with same name and overlapping input types: %s"
        % candidates
    )


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
        if fq_op_name == "index":
            # special case for index, which in weave python is always implemented as the
            # __getitem__ dunder method
            shared_name_ops += registry_mem.memory_registry.find_ops_by_common_name(
                op_def.common_name("__getitem__")
            )
    candidates: list[Candidate] = []
    for op in shared_name_ops:
        param_dict = op.input_type.create_param_dict(args, kwargs)
        param_dict = language_nullability.adjust_assignable_param_dict_for_dispatch(
            op, param_dict
        )
        assigned_param_dict = op.input_type.assign_param_dict(param_dict)
        if op_args.all_types_valid(assigned_param_dict):
            candidates.append(Candidate(op, assigned_param_dict))
    if len(candidates) > 1:
        return resolve_op_ambiguity(fq_op_name, candidates)
    if candidates:
        return candidates[0].op
    return None


class FallbackNodeTypeDispatcherMixin(weave_internal.UniversalNodeMixin):
    """
    Special Mixin class for dispatching arbirary property (attribute) access.
    This mixin should be included at the end of the MRO for a class that is a
    subclass of Node. (see `get_node_methods_classes`). The result is that when
    we have a node N, we can do dot chaining like `N.foo`. If no other node
    class in the MRO has a wayh to resolve `foo`, then this class will try to
    resolve it. First, we ignore dunder methods, then we determine if `foo`
    matches one or more ops for the given node. This matching must happen before
    the arguments are passed because if no match is found, then we want to
    return the general `obj_getattr` op (which is our general attribute
    accessort). However if at last one op matches the name, we return a function
    that will return an called op once executed. We need it to be lazy because
    it is possible that more than one op matches the name, and we need to
    further refine once we get inputs.
    """

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

    def __getattr__(self, attr: str) -> typing.Any:
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
                self.type
            ):
                if isinstance(self, graph.Node):
                    op.instance = self
                ops_with_name_and_arg.append(op)
        if len(ops_with_name_and_arg) > 0:
            # Here we just return the first op, since the op call itself will dispatch to the correct op
            # if needed
            return ops_with_name_and_arg[0]
        elif (
            isinstance(self.type, types.ObjectType) or self.type.__class__ == types.Type
        ):
            obj_getattr = registry_mem.memory_registry.get_op("Object-__getattr__")
            return obj_getattr(self, attr)
        return None


_default_dunders = [
    "__add__",
    "__sub__",
    "__mul__",
    "__divmod__",
    "__mod__",
    "__ge__",
    "__gt__",
    "__le__",
    "__ne__",
    "__lt__",
    "__abs__",
    "__len__",
    "__contains__",
    "__str__",
]


def _make_dunder(dunder_name: str) -> typing.Callable:
    # This is one of the few "hacks" in the dispatcher. Here, if we have
    # a dunder method coming in, we are in a wierd situation. This is
    # becuase the dunder methods don't have the same common name. For
    # example, __mul__ is actually called "mult". So here, we have two
    # hacks:
    # 1. We look for the NodeMethodsClass of the type (which may not
    #    exist - or may have been overridden...) and use the name of the
    #    dunder method there.
    # 2. If that doesn't exist, we do the same for the possible
    #    `object_type` inner type (which is convension for lists).
    #
    # TODO: This whole thing could be avoided and replaced if we
    # standardize a name mapping of dunder methods to op names
    def dunder(
        self: FallbackNodeTypeDispatcherMixin, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Any:
        attr = dunder_name
        if hasattr(self.type, "NodeMethodsClass") and hasattr(
            self.type.NodeMethodsClass, attr
        ):
            attr = getattr(self.type.NodeMethodsClass, attr).common_name
        elif (
            hasattr(self.type, "object_type")
            and hasattr(self.type.object_type, "NodeMethodsClass")
            and hasattr(self.type.object_type.NodeMethodsClass, attr)
        ):
            attr = getattr(self.type.object_type.NodeMethodsClass, attr).common_name
        op = self.__getattr__(attr)
        if isinstance(op, op_def.OpDef):
            return op(*args, **kwargs)
        else:
            raise AttributeError("No op found for dunder method %s" % dunder_name)

    return dunder


def _add_dunders_to_fallback_mixin() -> None:
    for dunder in _default_dunders:
        method = _make_dunder(dunder)
        setattr(
            FallbackNodeTypeDispatcherMixin, dunder, method
        )  # MethodType(method, FallbackNodeTypeDispatcherMixin))


_add_dunders_to_fallback_mixin()
