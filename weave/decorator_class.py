import inspect

from . import registry_mem
from . import op_def
from . import weave_types as types


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
                if opdef.name.startswith("op-"):
                    registry_mem.memory_registry.rename_op(
                        opdef.name,
                        "%s-%s"
                        % (
                            types.type_class_type_name(weave_type),
                            opdef.name[3:],
                        ),
                    )

        weave_type.NodeMethodsClass = target
        # Check __dict__ instead of using regular attribute access
        # because we want to add instance_classes even if it is already
        # set in a base class
        if weave_type.__dict__.get("instance_classes") is None:
            weave_type.instance_classes = target
            weave_type.instance_class = target
        return target

    return wrap
