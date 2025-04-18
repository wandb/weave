from typing import TYPE_CHECKING, Any, Union

import pydantic

if TYPE_CHECKING:
    from pydantic.v1 import BaseModel as PydanticBaseModelV1


def is_pydantic_v1_base_model(obj: Any) -> bool:
    try:
        from pydantic.v1 import BaseModel as PydanticBaseModelV1

        return isinstance(obj, PydanticBaseModelV1)
    except ImportError:
        return False


PydanticBaseModelGeneral = Union[pydantic.BaseModel, "PydanticBaseModelV1"]


def pydantic_model_fields(
    obj: PydanticBaseModelGeneral,
) -> dict[str, pydantic.fields.FieldInfo]:
    if isinstance(obj, pydantic.BaseModel):
        return obj.model_fields
    elif is_pydantic_v1_base_model(obj):
        return obj.__fields__
    else:
        raise TypeError(f"{obj} is not a pydantic model")


def pydantic_asdict_one_level(obj: PydanticBaseModelGeneral) -> dict[str, Any]:
    """
    This is equivalent to `obj.model_dump(by_alias=True)`, but does not recursively
    convert nested pydantic objects to dicts. This is particularly useful when you want
    manually iterate over the fields of a pydantic object and do something with them.
    """
    fields = pydantic_model_fields(obj)
    final = {}
    for prop_name, field in fields.items():
        use_name = prop_name
        # This odd check is to support different pydantic versions
        if hasattr(field, "exclude") and field.exclude:
            continue
        # This odd check is to support different pydantic versions
        if hasattr(field, "alias") and field.alias:
            use_name = field.alias
        final[use_name] = getattr(obj, prop_name)
    return final
