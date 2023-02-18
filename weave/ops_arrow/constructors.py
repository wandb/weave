import dataclasses
import pyarrow as pa
import typing

from .. import artifact_base
from .. import weave_types as types
from .. import box
from ..language_features.tagging import tag_store, tagged_value_type
from .. import errors

from .arrow import arrow_as_array, ArrowWeaveListType
from .list_ import ArrowWeaveList
from . import arrow_tags
from . import convert


def repeat(value: typing.Any, count: int) -> pa.Array:
    value_single = convert.to_arrow([value])._arrow_data
    return pa.repeat(value_single[0], count)


@dataclasses.dataclass
class VectorizedContainerConstructorResults:
    arrays: list[pa.Array]
    prop_types: dict[str, types.Type]
    max_len: int
    artifact: typing.Optional[artifact_base.Artifact]


def vectorized_input_types(input_types: dict[str, types.Type]) -> dict[str, types.Type]:
    prop_types: dict[str, types.Type] = {}
    for input_name, input_type in input_types.items():
        if isinstance(input_type, types.Const):
            input_type = input_type.val_type
        if isinstance(input_type, tagged_value_type.TaggedValueType) and (
            isinstance(input_type.value, ArrowWeaveListType)
            or types.is_list_like(input_type.value)
        ):
            outer_tag_type = input_type.tag
            object_type = input_type.value.object_type  # type: ignore
            if isinstance(object_type, tagged_value_type.TaggedValueType):
                new_prop_type = tagged_value_type.TaggedValueType(
                    types.TypedDict(
                        {
                            **outer_tag_type.property_types,
                            **object_type.tag.property_types,
                        }
                    ),
                    object_type.value,
                )
            else:
                new_prop_type = tagged_value_type.TaggedValueType(
                    outer_tag_type, object_type
                )
            prop_types[input_name] = new_prop_type
        elif isinstance(input_type, ArrowWeaveListType) or types.is_list_like(
            input_type
        ):
            prop_types[input_name] = input_type.object_type  # type: ignore
        else:  # is scalar
            prop_types[input_name] = input_type
    return prop_types


def vectorized_container_constructor_preprocessor(
    input_dict: dict[str, typing.Any]
) -> VectorizedContainerConstructorResults:
    if len(input_dict) == 0:
        return VectorizedContainerConstructorResults([], {}, 0, None)
    arrays = []
    prop_types = {}
    awl_artifact = None
    for k, v in input_dict.items():
        if isinstance(v, ArrowWeaveList):
            if awl_artifact is None:
                awl_artifact = v._artifact
            if tag_store.is_tagged(v):
                list_tags = tag_store.get_tags(v)
                # convert tags to arrow
                v = arrow_tags.tag_awl_list_elements_with_single_tag_dict(v, list_tags)
            prop_types[k] = v.object_type
            v = v._arrow_data
            arrays.append(arrow_as_array(v))
        else:
            prop_types[k] = types.TypeRegistry.type_of(v)
            arrays.append(v)

    # array len of None means we have a scalar
    array_lens: list[typing.Optional[int]] = []
    for a, t in zip(arrays, prop_types.values()):
        if hasattr(a, "to_pylist"):
            array_lens.append(len(a))
        else:
            array_lens.append(None)

    if all(l is None for l in array_lens):
        max_len = 1
    else:
        max_len = max(a for a in array_lens if a is not None)

    for l in array_lens:
        if l is not None and l != max_len:
            raise errors.WeaveInternalError(
                f"Cannot create ArrowWeaveDict with different length arrays (scalars are ok): {array_lens}"
            )

    for i, (a, l) in enumerate(zip(arrays, array_lens)):
        if l is None:
            tags: typing.Optional[dict] = None
            if tag_store.is_tagged(a):
                tags = tag_store.get_tags(a)
            if box.is_boxed(a):
                a = box.unbox(a)
            arrays[i] = repeat(a, max_len)
            if tags is not None:
                arrays[i] = arrow_tags.tag_arrow_array_elements_with_single_tag_dict(
                    arrays[i], tags
                )

    return VectorizedContainerConstructorResults(
        arrays, prop_types, max_len, awl_artifact
    )
