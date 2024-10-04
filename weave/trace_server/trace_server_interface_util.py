import base64
import hashlib
import typing

from weave.trace_server import refs_internal

TRACE_REF_SCHEME = "weave"
ARTIFACT_REF_SCHEME = "wandb-artifact"
WILDCARD_ARTIFACT_VERSION_AND_PATH = ":*"


def bytes_digest(json_val: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(json_val)
    hash_bytes = hasher.digest()
    base64_encoded_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64_encoded_hash.replace("-", "X").replace("_", "Y").rstrip("=")


def str_digest(json_val: str) -> str:
    return bytes_digest(json_val.encode())


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


valid_schemes = [
    TRACE_REF_SCHEME,
    ARTIFACT_REF_SCHEME,
    refs_internal.WEAVE_INTERNAL_SCHEME,
]


def extract_refs_from_values(
    vals: typing.Any,
) -> typing.List[str]:
    refs = []

    def _visit(val: typing.Any) -> typing.Any:
        if isinstance(val, dict):
            for v in val.values():
                _visit(v)
        elif isinstance(val, list):
            for v in val:
                _visit(v)
        elif isinstance(val, str) and any(
            val.startswith(scheme + "://") for scheme in valid_schemes
        ):
            refs.append(val)

    _visit(vals)
    return refs


def assert_non_null_wb_user_id(obj: typing.Any) -> None:
    if not hasattr(obj, "wb_user_id") or obj.wb_user_id is None:
        raise ValueError("wb_user_id cannot be None")


def assert_null_wb_user_id(obj: typing.Any) -> None:
    if hasattr(obj, "wb_user_id") and obj.wb_user_id is not None:
        raise ValueError("wb_user_id must be None")
