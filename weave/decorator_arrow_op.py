import typing

from . import weave_types as types
from .language_features.tagging import tagged_value_type
from .ops_arrow.arrow import ArrowWeaveListType
from . import op_def
from .decorator_op import op

TypeCallable = typing.Callable[..., types.Type]
TypeOrCallable = typing.Union[types.Type, TypeCallable]
InputTypeDict = typing.Mapping[str, TypeOrCallable]


def _nullify_vector_type(t: types.Type) -> types.Type:
    if isinstance(t, ArrowWeaveListType):
        return ArrowWeaveListType(types.optional(t.object_type))
    elif isinstance(t, types.List):
        return types.List(types.optional(t.object_type))
    elif isinstance(t, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueType(t.tag, _nullify_vector_type(t.value))
    elif isinstance(t, types.UnionType):
        return types.UnionType(*[_nullify_vector_type(mem) for mem in t.members])
    else:
        return types.optional(t)


def _make_nullable_vector_input_type_callable(
    old_type_func: TypeCallable,
) -> TypeCallable:
    def new_callable_nullable_awl_type(
        non_callable_input_types: dict[str, types.Type]
    ) -> types.Type:
        old_type = old_type_func(non_callable_input_types)
        return _nullify_vector_type(old_type)

    return new_callable_nullable_awl_type


def adjust_input_types_for_nullability(
    input_types: InputTypeDict, all_args_nullable: bool
) -> InputTypeDict:
    new_input_type_dict: dict[str, typing.Any] = {}
    for i, key in enumerate(input_types):
        if i == 0 or all_args_nullable:
            if callable(input_types[key]):
                new_input_type_dict[key] = _make_nullable_vector_input_type_callable(
                    typing.cast(TypeCallable, input_types[key])
                )
            else:
                new_input_type_dict[key] = _nullify_vector_type(
                    typing.cast(types.Type, input_types[key])
                )
        else:
            new_input_type_dict[key] = input_types[key]
    return typing.cast(InputTypeDict, new_input_type_dict)


def _handle_arrow_tags(
    old_output_type: ArrowWeaveListType, first_input_type: ArrowWeaveListType
) -> types.Type:
    if isinstance(first_input_type.object_type, tagged_value_type.TaggedValueType):
        return ArrowWeaveListType(
            tagged_value_type.TaggedValueType(
                first_input_type.object_type.tag, old_output_type.object_type
            )
        )
    return old_output_type


def _make_new_vector_output_type_callable(
    old_type_func: TypeCallable, is_null_consuming=False
) -> TypeCallable:
    def new_callable_nullable_awl_type(
        non_callable_input_types: dict[str, types.Type]
    ) -> types.Type:
        first_input_type_name = next(k for k in non_callable_input_types)
        first_input_type = non_callable_input_types[first_input_type_name]
        assert ArrowWeaveListType().assign_type(first_input_type)
        first_input_type = typing.cast(ArrowWeaveListType, first_input_type)

        has_optional_vector_type = types.is_optional(first_input_type.object_type)
        if has_optional_vector_type and not is_null_consuming:
            first_input_type = ArrowWeaveListType(
                types.non_none(first_input_type.object_type)
            )
            non_callable_input_types[first_input_type_name] = first_input_type

        old_type = typing.cast(
            ArrowWeaveListType, old_type_func(non_callable_input_types)
        )

        tag_propagated_output_type = _handle_arrow_tags(old_type, first_input_type)

        if has_optional_vector_type and not is_null_consuming:
            return _nullify_vector_type(tag_propagated_output_type)
        return tag_propagated_output_type

    return new_callable_nullable_awl_type


def adjust_output_type_for_tags_and_nullability(
    output_type: TypeOrCallable,
    is_null_consuming=False,
) -> TypeOrCallable:
    if not callable(output_type):
        new_output_type = typing.cast(TypeCallable, lambda _: output_type)
    else:
        new_output_type = typing.cast(TypeCallable, output_type)
    return _make_new_vector_output_type_callable(
        new_output_type, is_null_consuming=is_null_consuming
    )


def is_null_consuming_arrow_op(input_types: InputTypeDict) -> bool:
    first_input_type_name = next(k for k in input_types)
    first_input_type = input_types[first_input_type_name]
    assert not callable(first_input_type)
    assert ArrowWeaveListType().assign_type(first_input_type)
    return types.is_optional(
        typing.cast(ArrowWeaveListType, first_input_type).object_type
    )


def arrow_op(
    input_type: InputTypeDict,
    output_type: TypeOrCallable,
    refine_output_type=None,
    name=None,
    setter=None,
    render_info=None,
    pure=True,
    all_args_nullable: bool = True,
    plugins=None,
) -> typing.Callable[[typing.Any], op_def.OpDef]:
    """An arrow op is an op that should obey element-based tag-flow map rules. An arrow op must

    1) Have a first arg that is an ArrowWeaveList.
    2) Output an ArrowWeaveList with the same shape as (1)
    3) Each element of the output should represent a mapped transform of the input

    In these cases, element tags from (1) are automatically propagated to each element of (2).
    """

    # TODO(DG): handle reading input and output types from function signature
    is_null_consuming = is_null_consuming_arrow_op(input_type)
    if not is_null_consuming:
        new_input_type = adjust_input_types_for_nullability(
            input_type, all_args_nullable
        )
    else:
        new_input_type = input_type
    new_output_type = adjust_output_type_for_tags_and_nullability(
        output_type, is_null_consuming=is_null_consuming
    )

    return op(
        input_type=new_input_type,
        output_type=new_output_type,
        refine_output_type=refine_output_type,
        name=name,
        setter=setter,
        render_info=render_info,
        pure=pure,
        _op_def_class=op_def.AutoTagHandlingArrowOpDef,
        plugins=plugins,
    )
