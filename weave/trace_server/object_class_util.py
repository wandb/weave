from typing import Any, Optional, TypedDict

from pydantic import BaseModel

from weave.trace_server.client_server_common.pydantic_util import (
    pydantic_asdict_one_level,
)
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY,
)

"""
There are two standard base object classes: BaseObject and Object

`Object` is the base class for the more advanced object-oriented `weave.Object` use cases.
`BaseObject` is the more simple schema-based base object class.
"""
base_object_class_names = ["BaseObject", "Object"]


class GetObjectClassesResult(TypedDict):
    # object_class is the "leaf" class of the val assuming it is a subclass of weave.Object or weave.BaseObject
    object_class: Optional[str]
    # base_object_class is the first subclass of weave.Object or weave.BaseObject
    base_object_class: Optional[str]


def get_object_classes(val: Any) -> Optional[GetObjectClassesResult]:
    if isinstance(val, dict):
        if "_bases" in val:
            if isinstance(val["_bases"], list):
                if len(val["_bases"]) >= 2:
                    if val["_bases"][-1] == "BaseModel":
                        if val["_bases"][-2] in base_object_class_names:
                            object_class = val["_class_name"]
                            base_object_class = object_class
                            if len(val["_bases"]) > 2:
                                base_object_class = val["_bases"][-3]
                            return GetObjectClassesResult(
                                object_class=object_class,
                                base_object_class=base_object_class,
                            )
    return None


class ProcessIncomingObjectResult(TypedDict):
    val: Any
    base_object_class: Optional[str]


def process_incoming_object_val(
    val: Any, req_builtin_object_class: Optional[str] = None
) -> ProcessIncomingObjectResult:
    """
    This method is responsible for accepting an incoming object from the user and validating it
    against the object class. It adds the _class_name and _bases keys correctly and returns the object
    with the base object class set. It does not mutate the original object, but returns a new object
    with values set if needed.
    """
    # First, we ensure the object is a dict before processing it.
    # If the object is not a dict, we return it as is and set the base_object_class to None.
    if not isinstance(val, dict):
        if req_builtin_object_class is not None:
            raise ValueError("object_class cannot be provided for non-dict objects")
        return ProcessIncomingObjectResult(val=val, base_object_class=None)

    # Next we extract the object classes from the object. the `_bases` and `_class_name` keys are
    # special weave-added keys that tell us the class hierarchy of the object.
    # _class_name is the name of the class of the object.
    # _bases is a list of the class's superclasses.
    # In the specific case that bases starts with `BaseModel` (Pydantic Root) and the next subclass
    # is in `base_object_class_names`, then we assume it is a special Weave Object class. From there,
    # we can extract the object class and base object class.
    val_object_classes = get_object_classes(val)

    # In the event that we successfully extracted the object classes, we need to check if the
    # requested object class matches the object class of the object. If it does not, we raise an error.
    if val_object_classes:
        if req_builtin_object_class:
            if val_object_classes["object_class"] != req_builtin_object_class:
                raise ValueError(
                    f"object_class must match val's defined object class: {val_object_classes['object_class']} != {req_builtin_object_class}"
                )
            else:
                # Note: instead of passing here, it is reasonable to conclude that we should instead raise an error -
                # effectively disallowing the user from providing both a requested object class and a class hierarchy inside the payload.
                pass
        # In this case, we assume that the object is valid and do not need to process it.
        # This would happen in practice if the user is editing an existing object by simply modifying the keys.
        return ProcessIncomingObjectResult(
            val=val, base_object_class=val_object_classes["base_object_class"]
        )

    # Next, we check if the user provided an object class. If they did, we need to validate the object
    # and set the correct bases information. This is an important case: the user is asking us to ensure that they payload is valid and
    # stored correctly. We need to validate the payload and write the correct bases information.
    if req_builtin_object_class is not None:
        if builtin_object_class := BUILTIN_OBJECT_REGISTRY.get(
            req_builtin_object_class
        ):
            # TODO: in the next iteration of this code path, this is where we need to actually publish the object
            # using the weave publish API instead of just dumping it.
            dict_val = dump_object(builtin_object_class.model_validate(val))
            new_val_object_classes = get_object_classes(dict_val)
            if not new_val_object_classes:
                raise ValueError(
                    f"Unexpected error: could not get object classes for {dict_val}"
                )
            if new_val_object_classes["object_class"] != req_builtin_object_class:
                raise ValueError(
                    f"Unexpected error: base object class does not match requested object class: {new_val_object_classes['object_class']} != {req_builtin_object_class}"
                )
            return ProcessIncomingObjectResult(
                val=dict_val,
                base_object_class=new_val_object_classes["base_object_class"],
            )
        else:
            raise ValueError(f"Unknown object class: {req_builtin_object_class}")

    # Finally, if there is no requested object class, just return the object as is.
    return ProcessIncomingObjectResult(val=val, base_object_class=None)


# Server-side version of `pydantic_object_record`
def dump_object(val: BaseModel) -> dict:
    cls = val.__class__
    cls_name = val.__class__.__name__
    bases = [c.__name__ for c in cls.mro()[1:-1]]

    dump = {}
    # Order matters here due to the way we calculate the digest!
    # This matches the client
    dump["_type"] = cls_name
    d = pydantic_asdict_one_level(val)
    for k, v in d.items():
        dump[k] = _general_dump(v)
    # yes, this is done twice, to match the client
    dump["_class_name"] = cls_name
    dump["_bases"] = bases
    return dump


def _general_dump(val: Any) -> Any:
    """
    This is a helper function that dumps a value into a dict. It is used to convert
    pydantic objects to dicts in a recursive manner.
    """
    if isinstance(val, BaseModel):
        return dump_object(val)
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
