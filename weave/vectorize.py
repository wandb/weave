from . import errors
from .ops_primitives import arrow
from . import op_def
from . import decorator_op
from . import weave_types as types
from . import artifacts_local

import typing


def _make_vectorized_constructor_ops() -> None:

    constructors: list[typing.Tuple[str, op_def.OpDef]] = []
    for object_type in types.ObjectType.__subclasses__():
        for instance_class in (
            object_type.instance_classes
            if isinstance(object_type.instance_classes, list)
            else [object_type.instance_classes]  # type: ignore
        ):
            if instance_class is None:
                raise errors.WeaveInternalError(
                    "Cannot vectorize constructor of op with no instance_class"
                )
            if hasattr(instance_class, "constructor"):
                constructors.append(
                    (typing.cast(str, object_type.name), instance_class.constructor)  # type: ignore
                )

    for type_name, constructor in constructors:

        # need to define a IIFE to capture the constructor output_type variable for the op resolver,
        # which is passed as argument 2 to ArrowWeaveList in the op resolver below
        def register_constructor() -> None:
            output_type = arrow.ArrowWeaveListType(
                typing.cast(types.Type, constructor.output_type)
            )

            @decorator_op.op(
                name=f'ArrowWeaveList-{type_name.replace("-", "_")}',
                input_type={
                    "attributes": arrow.ArrowWeaveListType(
                        constructor.input_type.weave_type().property_types["attributes"]  # type: ignore
                    )
                },
                output_type=output_type,
                render_info={"type": "function"},
            )
            def vectorized_constructor(attributes):
                return arrow.ArrowWeaveList(
                    attributes._arrow_data, output_type.object_type
                )

        register_constructor()
