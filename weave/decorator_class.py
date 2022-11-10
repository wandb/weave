import inspect

from . import registry_mem
from . import op_def
from . import derive_op
from . import errors
from . import weave_types as types

# Contrary to the way it is read, the weave.class() decorator runs AFTER the
# inner methods are defined. Therefore, this function runs after the ops are
# defined/registered. The majority of the logic here is to update those ops (and
# any derived ops) with proper names and types.


def weave_class(weave_type: type[types.Type]):
    def wrap(target):
        # add self type to input_types if its not already defined.
        for _, member in inspect.getmembers(target):
            if isinstance(member, op_def.OpDef):
                opdef = member
                self_type = opdef.input_type.arg_types.get("self")
                if self_type is not None and self_type == types.UnknownType():
                    opdef.input_type.arg_types["self"] = weave_type()
                # Replace function op names with method op names
                current_name = opdef.name
                requires_rename = current_name.startswith("op-")
                if requires_rename:
                    new_name = "%s-%s" % (
                        types.type_class_type_name(weave_type),
                        current_name[3:],
                    )
                    registry_mem.memory_registry.rename_op(
                        current_name,
                        new_name,
                    )

                for derived_handler_id, op in member.derived_ops.items():
                    handler = derive_op.handler_for_id(derived_handler_id)
                    handler.handle_class_decorator_update(op, weave_type, current_name)

                # After we rename the op, create any derived ops
                derive_op.derive_ops(opdef)

        weave_type.NodeMethodsClass = target
        # Check __dict__ instead of using regular attribute access
        # because we want to add instance_classes even if it is already
        # set in a base class
        if weave_type.__dict__.get("instance_classes") is None:
            weave_type.instance_classes = target
            weave_type.instance_class = target
        return target

    return wrap
