from typing import Any, Union

import pydantic

PydanticBaseModelGeneral = Union[pydantic.BaseModel, pydantic.v1.BaseModel]


def pydantic_model_fields(
    obj: PydanticBaseModelGeneral,
) -> dict[str, pydantic.fields.FieldInfo]:
    if isinstance(obj, pydantic.BaseModel):
        return obj.model_fields
    elif isinstance(obj, pydantic.v1.BaseModel):
        return obj.__fields__
    else:
        raise TypeError(f"{obj} is not a pydantic model")


def pydantic_asdict_one_level(obj: PydanticBaseModelGeneral) -> dict[str, Any]:
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
