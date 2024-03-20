from typing import Any

from weave import box
from weave.chobj import custom_objs
from weave.trace.refs import ObjectRef, TableRef, parse_uri
from weave.trace.object_record import ObjectRecord


def to_json(obj: Any) -> Any:
    if isinstance(obj, TableRef):
        return obj.uri()
    elif isinstance(obj, ObjectRef):
        return obj.uri()
    elif isinstance(obj, ObjectRecord):
        res = {"_type": obj._class_name}
        for k, v in obj.__dict__.items():
            res[k] = to_json(v)
        return res
    elif isinstance(obj, list):
        return [to_json(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}

    if isinstance(obj, (int, float, str, bool, box.BoxedNone)) or obj is None:
        return obj

    return custom_objs.encode_custom_obj(obj)


def from_json(obj: Any) -> Any:
    if isinstance(obj, list):
        return [from_json(v) for v in obj]
    elif isinstance(obj, dict):
        val_type = obj.get("_type")
        if val_type is not None:
            del obj["_type"]
            if val_type == "ObjectRecord":
                return ObjectRecord({k: from_json(v) for k, v in obj.items()})
            elif val_type == "CustomWeaveType":
                return custom_objs.decode_custom_obj(obj["weave_type"], obj["files"])
            else:
                return ObjectRecord({k: from_json(v) for k, v in obj.items()})
        return {k: from_json(v) for k, v in obj.items()}
    elif isinstance(obj, str) and obj.startswith("weave://"):
        return parse_uri(obj)

    return obj
