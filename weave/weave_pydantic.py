from pydantic import BaseModel, create_model
from . import weave_types as types


def weave_type_to_pydantic(
    property_types: dict[str, types.Type], name: str
) -> BaseModel:
    field_types = {}
    for k, v in property_types.items():
        if isinstance(v, types.TypedDict):
            field_types[k] = weave_type_to_pydantic(v.property_types, "TypedDict")
        else:
            instance_classes = v._instance_classes()
            if not instance_classes:
                raise ValueError(f"Cannot convert {v} to pydantic")
            field_types[k] = instance_classes[0]  # type: ignore
    field_defs = {k: (v, ...) for k, v in field_types.items()}
    return create_model(name, **field_defs)  # type: ignore
