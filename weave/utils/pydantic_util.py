from typing import Any

from pydantic import BaseModel


def pydantic_asdict_one_level(obj: BaseModel) -> dict[str, Any]:
    """This is equivalent to `obj.model_dump(by_alias=True)`, but does not recursively
    convert nested pydantic objects to dicts. This is particularly useful when you want
    manually iterate over the fields of a pydantic object and do something with them.
    """
    fields = obj.__class__.model_fields
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
