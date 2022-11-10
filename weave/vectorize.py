from . import errors
from .ops_primitives import arrow
from . import op_def
from . import decorator_op
from . import weave_types as types

import typing


def make_register_constructor_fn(
    constructor: op_def.OpDef, type_name: str
) -> typing.Callable[[], None]:
    def register_constructor() -> None:
        output_type: typing.Union[
            types.Type, typing.Callable[[typing.Dict[str, types.Type]], types.Type]
        ]
        if callable(constructor.output_type):
            callable_output_type = constructor.output_type

            def output_type_fn(input_types: typing.Dict[str, types.Type]) -> types.Type:
                return arrow.ArrowWeaveListType(callable_output_type(input_types))

            output_type = output_type_fn
        else:
            output_type = arrow.ArrowWeaveListType(constructor.output_type)

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
            if callable(output_type):
                ot = output_type({"attributes": types.TypeRegistry.type_of(attributes)})
            else:
                ot = output_type
            return arrow.ArrowWeaveList(attributes._arrow_data, ot.object_type)

    return register_constructor


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
        make_register_constructor_fn(constructor, type_name)()
