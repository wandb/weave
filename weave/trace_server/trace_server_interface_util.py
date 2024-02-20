import hashlib
import json
import uuid
from . import trace_server_interface as tsi


# This is a quick solution but needs more thought


def version_hash_for_object(obj: tsi.PartialObjForCreationSchema) -> str:
    type_dict = _order_dict(obj.type_dict)
    # val_dict = _order_dict(obj.val_dict)

    hasher = hashlib.md5()
    
    hasher.update(json.dumps(type_dict).encode())
    # hasher.update(json.dumps(val_dict).encode())

    files = _order_dict(obj.encoded_file_map or {})
    for k, v in files.items():
        hasher.update(k.encode())
        if isinstance(v, str):
            hasher.update(v.encode())
        elif isinstance(v, bytes):
            hasher.update(v)
        else:
            raise ValueError(f"Unexpected type for file {k}: {type(v)}")

    return hasher.hexdigest()

# def version_hash_for_op(op: tsi.PartialOpForCreationSchema) -> str:

#     hasher = hashlib.md5()
#     hasher.update(op.name.encode())
#     if op.code:
#         hasher.update(op.code.encode())
#     if op.environment_state_identity:
#         hasher.update(op.environment_state_identity.encode())
    
#     return hasher.hexdigest()


def _decode_bytes_to_str(dictionary):
    return {
        k: _decode_bytes_to_str(v)
        if isinstance(v, dict)
        else v.decode()
        if isinstance(v, bytes)
        else v
        for k, v in dictionary.items()
    }


def _order_dict(dictionary):
    return {
        k: _order_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(dictionary.items())
    }
