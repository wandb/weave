import inspect
import typing

from weave import errors, registry_mem
from weave import weave_types as types
from weave.legacy import context_state, derive_op, op_def

# Contrary to the way it is read, the weave.class() decorator runs AFTER the
# inner methods are defined. Therefore, this function runs after the ops are
# defined/registered. The majority of the logic here is to update those ops (and
# any derived ops) with proper names and types.


def weave_class(weave_type: type[types.Type]):
    def wrap(target):
        # add self type to input_types if its not already defined.
        for _, member in inspect.getmembers(target):
            if isinstance(member, op_def.BoundOpDef):
                opdef = typing.cast(op_def.BoundOpDef, member)
                self_type = opdef.input_type.arg_types.get("self")
                if self_type is not None and self_type == types.UnknownType():
                    opdef.input_type.arg_types["self"] = weave_type()
                    # Now that we have a self_type, we may be able to derive
                    # ops.
                    derive_op.derive_ops(opdef)
                # Replace function op names with method op names
                current_name = opdef.name
                requires_rename = current_name.startswith("op-")
                if requires_rename:
                    new_name = "%s-%s" % (
                        weave_type.name,
                        current_name[3:],
                    )
                    loading_builtins = context_state._loading_built_ins.get()
                    if loading_builtins:
                        registry_mem.memory_registry.rename_op(
                            current_name,
                            new_name,
                        )

                        for derived_handler_id, op in member.derived_ops.items():
                            handler = derive_op.handler_for_id(derived_handler_id)
                            handler.handle_class_decorator_update(
                                op, weave_type, new_name
                            )
                    else:
                        opdef.op_def.name = new_name

        # Check __dict__ instead of using regular attribute access
        # because we want to add instance_classes even if it is already
        # set in a base class
        if weave_type.__dict__.get("instance_classes") is None:
            weave_type.instance_classes = target
            weave_type.instance_class = target
        return target

    return wrap
