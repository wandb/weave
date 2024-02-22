import base64
import hashlib
import json
import typing
import uuid

from . import trace_server_interface as tsi


def generate_id() -> str:
    return str(uuid.uuid4())


# This is a quick solution but needs more thought
def version_hash_for_object(obj: tsi.ObjSchemaForInsert) -> str:
    hasher = hashlib.md5()

    hasher.update(json.dumps(_order_dict(obj.type_dict)).encode())
    # until updates are supported, we need to hash the metadata_dict
    hasher.update(json.dumps(_order_dict(obj.metadata_dict)).encode())
    hasher.update(json.dumps(_order_dict(obj.b64_file_map)).encode())

    return hasher.hexdigest()


def _order_dict(dictionary: typing.Dict) -> typing.Dict:
    return {
        k: _order_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(dictionary.items())
    }


def encode_bytes_as_b64(contents: typing.Dict[str, bytes]) -> typing.Dict[str, str]:
    res = {}
    for k, v in contents.items():
        if isinstance(v, bytes):
            res[k] = base64.b64encode(v).decode("ascii")
        else:
            raise ValueError(f"Unexpected type for file {k}: {type(v)}")
    return res


def decode_b64_to_bytes(contents: typing.Dict[str, str]) -> typing.Dict[str, bytes]:
    res = {}
    for k, v in contents.items():
        if isinstance(v, str):
            res[k] = base64.b64decode(v.encode("ascii"))
        else:
            raise ValueError(f"Unexpected type for file {k}: {type(v)}")
    return res
