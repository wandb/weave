import dataclasses

from . import weave_types as types
from . import infer_types
from . import decorator_class

_py_type = type


def make_type_maker(dc, target_name, property_types):
    # type_hints = typing.get_type_hints(f)

    # ##### Input type processing

    # python_input_type = copy.copy(type_hints)
    # if "return" in python_input_type:
    #     python_input_type.pop("return")

    # declared_input_type = input_type
    # if declared_input_type is None:
    #     declared_input_type = {}
    # weave_input_type = _create_args_from_op_input_type(declared_input_type)

    # if weave_input_type.kind == op_args.OpArgs.NAMED_ARGS:
    #     arg_names = get_signature(f).parameters.keys()

    #     # validate there aren't extra declared Weave types
    #     weave_type_extra_arg_names = set(weave_input_type.arg_types.keys()) - set(
    #         arg_names
    #     )
    #     if weave_type_extra_arg_names:
    #         raise errors.WeaveDefinitionError(
    #             "Weave Types declared for non-existent args: %s."
    #             % weave_type_extra_arg_names
    #         )

    #     arg_types = {}

    #     # iterate through function args in order. The function determines
    #     # the order of arg_types, which is relied on everywhere.
    # for input_name in arg_names:
    #     python_type = python_input_type.get(input_name)
    #     existing_weave_type = weave_input_type.arg_types.get(input_name)
    #     if python_type is not None:
    #         inferred_type = infer_types.python_type_to_type(python_type)
    #         if inferred_type == types.UnknownType():
    #             raise errors.WeaveDefinitionError(
    #                 "Weave Type could not be determined from Python type (%s) for arg: %s."
    #                 % (python_type, input_name)
    #             )
    #         if existing_weave_type and existing_weave_type != inferred_type:
    #             raise errors.WeaveDefinitionError(
    #                 "Python type (%s) and Weave Type (%s) declared for arg: %s. Remove one of them to fix."
    #                 % (inferred_type, existing_weave_type, input_name)
    #             )
    #         arg_types[input_name] = inferred_type
    #     elif existing_weave_type:
    #         arg_types[input_name] = existing_weave_type
    #     else:
    #         arg_types[input_name] = types.UnknownType()

    #     # validate there aren't missing Weave types
    #     unknown_type_args = set(
    #         arg_name
    #         for arg_name, at in arg_types.items()
    #         if at == types.UnknownType()
    #     )
    #     weave_type_missing_arg_names = unknown_type_args - {"self", "_run"}
    #     if weave_type_missing_arg_names:
    #         raise errors.WeaveDefinitionError(
    #             "Missing Weave Types for args: %s." % weave_type_missing_arg_names
    #         )

    #     weave_input_type = op_args.OpNamedArgs(arg_types)
    # else:
    #     # TODO: no validation here...
    #     pass

    # ##### Output type processing

    # python_return_type = type_hints.get("return")
    # if python_return_type is None:
    #     inferred_output_type = types.UnknownType()
    # else:
    #     inferred_output_type = infer_types.python_type_to_type(python_return_type)
    #     if inferred_output_type == types.UnknownType():
    #         raise errors.WeaveDefinitionError(
    #             "Could not infer Weave Type from declared Python return type: %s"
    #             % python_return_type
    #         )

    # weave_output_type = output_type
    # if weave_output_type is None:
    #     # weave output type is not declared, use type inferred from Python
    #     weave_output_type = inferred_output_type
    # else:
    #     # Weave output_type was declared. Ensure compatibility with Python type.
    #     if callable(weave_output_type):
    #         if inferred_output_type != types.UnknownType():
    #             raise errors.WeaveDefinitionError(
    #                 "output_type is function but Python return type also declared. This is not yet supported"
    #             )
    #     elif (
    #         inferred_output_type != types.UnknownType()
    #         and weave_output_type.assign_type(inferred_output_type)
    #         == types.Invalid()
    #     ):
    #         raise errors.WeaveDefinitionError(
    #             "Python return type not assignable to declared Weave output_type: %s !-> %s"
    #             % (inferred_output_type, weave_output_type)
    #         )
    # if not callable(weave_output_type) and weave_output_type == types.UnknownType():
    #     raise errors.WeaveDefinitionError(
    #         "Op's return type must be declared: %s" % f
    #     )

    # fq_op_name = name
    # if fq_op_name is None:
    #     fq_op_name = "op-%s" % f.__name__
    #     # Don't use fully qualified names (which are URIs) for
    #     # now.
    #     # Ah crap this isn't right yet.
    #     # fq_op_name = op_def.fully_qualified_opname(f)

    # TODO: mak this an exec
    def func_name_maker(attr):
        return dc(attr)

    f = func_name_maker  # lambda *args, **kwargs: dc(*args, **kwargs)
    weave_output_type = dc  # or dc.WeaveType
    from . import op_def
    from . import registry_mem
    from weave.decorators import _create_args_from_op_input_type

    print(property_types)
    op = op_def.OpDef(
        target_name,
        _create_args_from_op_input_type(property_types),
        weave_output_type,
        f,
        refine_output_type=None,
        setter=None,
        render_info={"type": "function"},
        pure=True,
    )

    op_version = registry_mem.memory_registry.register_op(op)
    return op_version


def type(__override_name: str = None):
    def wrap(target):
        dc = dataclasses.dataclass(target)
        fields = dataclasses.fields(dc)
        target_name = target.__name__
        if __override_name is not None:
            target_name = __override_name

        TargetType = _py_type(f"{target_name}Type", (types.ObjectType,), {})
        TargetType.name = target_name
        TargetType.instance_classes = target
        TargetType.instance_class = target
        TargetType.NodeMethodsClass = dc

        property_types = {
            field.name: infer_types.python_type_to_type(field.type) for field in fields
        }

        # If there are any variable type properties, make them variable
        # in the type we are creating.
        for name, prop_type in property_types.items():
            prop_type_vars = prop_type.type_vars
            if callable(prop_type_vars):
                prop_type_vars = prop_type_vars()
            if len(prop_type_vars):
                setattr(TargetType, name, prop_type)
                setattr(TargetType, "__annotations__", {})
                TargetType.__dict__["__annotations__"][name] = types.Type

        def property_types_method(self):
            return property_types

        TargetType.property_types = property_types_method
        TargetType = dataclasses.dataclass(TargetType)

        dc.WeaveType = TargetType
        decorator_class.weave_class(weave_type=TargetType)(dc)
        # tm = make_type_maker(dc, target_name, property_types)
        # dc.init = tm
        return dc

    return wrap
