from typing import Any, Optional

from pydantic import BaseModel

from weave.trace_server.interface.base_object_classes.base_object_registry import (
    BASE_OBJECT_REGISTRY,
)

"""
There are two standard base object classes: BaseObject and Object

`Object` is the base class for the more advanced object-oriented `weave.Object` use cases.
`BaseObject` is the more simple schema-based base object class.
"""
base_object_class_names = ["BaseObject", "Object"]


def get_base_object_class(val: Any) -> Optional[str]:
    if isinstance(val, dict):
        if "_bases" in val:
            if isinstance(val["_bases"], list):
                if len(val["_bases"]) >= 2:
                    if val["_bases"][-1] == "BaseModel":
                        if val["_bases"][-2] in base_object_class_names:
                            if len(val["_bases"]) > 2:
                                return val["_bases"][-3]
                            elif "_class_name" in val:
                                return val["_class_name"]
    return None


def process_incoming_object(
    val: Any, req_base_object_class: Optional[str] = None
) -> tuple[dict, Optional[str]]:
    """
    This method is responsible for accepting an incoming object from the user, validating it
    against the base object class, and returning the object with the base object class
    set. It does not mutate the original object, but returns a new object with values set if needed.

    Specifically,:

    1. If the object is not a dict, it is returned as is, and the base object class is set to None.
    2. There are 2 ways to specify the base object class:
        a. The `req_base_object_class` argument.
            * used by non-pythonic writers of weave objects
        b. The `_bases` & `_class_name` attributes of the object, which is a list of base class names.
            * used by pythonic weave object writers (legacy)
    3. If the object has a base object class that does not match the requested base object class,
        an error is thrown.
    4. if the object contains a base object class inside the payload, then we simply validate
        the object against the base object class (if a match is found in BASE_OBJECT_REGISTRY)
    5. If the object does not have a base object class and a requested base object class is
        provided, we require a match in BASE_OBJECT_REGISTRY and validate the object against
        the requested base object class. Finally, we set the correct feilds.
    """
    if not isinstance(val, dict):
        if req_base_object_class is not None:
            raise ValueError(
                "set_base_object_class cannot be provided for non-dict objects"
            )
        return val, None

    dict_val = val.copy()
    val_base_object_class = get_base_object_class(dict_val)

    if (
        val_base_object_class != None
        and req_base_object_class != None
        and val_base_object_class != req_base_object_class
    ):
        raise ValueError(
            f"set_base_object_class must match base_object_class: {val_base_object_class} != {req_base_object_class}"
        )

    if val_base_object_class is not None:
        # In this case, we simply validate if the match is found
        if base_object_class_type := BASE_OBJECT_REGISTRY.get(val_base_object_class):
            base_object_class_type.model_validate(dict_val)
    elif req_base_object_class is not None:
        # In this case, we require that the base object class is registered
        if base_object_class_type := BASE_OBJECT_REGISTRY.get(req_base_object_class):
            dict_val = dump_base_object(base_object_class_type.model_validate(dict_val))
        else:
            raise ValueError(f"Unknown base object class: {req_base_object_class}")

    base_object_class = val_base_object_class or req_base_object_class

    return dict_val, base_object_class


# Server-side version of `pydantic_object_record`
def dump_base_object(val: BaseModel) -> dict:
    cls = val.__class__
    cls_name = val.__class__.__name__
    bases = [c.__name__ for c in cls.mro()[1:-1]]

    dump = {}
    # Order matters here due to the way we calculate the digest!
    # This matches the client
    dump["_type"] = cls_name
    for k in val.model_fields:
        dump[k] = _general_dump(getattr(val, k))
    # yes, this is done twice, to match the client
    dump["_class_name"] = cls_name
    dump["_bases"] = bases
    return dump


def _general_dump(val: Any) -> Any:
    if isinstance(val, BaseModel):
        return dump_base_object(val)
    elif isinstance(val, dict):
        return {k: _general_dump(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_general_dump(v) for v in val]
    elif isinstance(val, tuple):
        return tuple(_general_dump(v) for v in val)
    elif isinstance(val, set):
        return {_general_dump(v) for v in val}
    else:
        return val
