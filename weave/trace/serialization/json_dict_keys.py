"""Convert values to JSON with dict keys written the way the digest writes them."""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter
from pydantic_core import to_jsonable_python

from weave.trace.serialization.digest import _has_non_string_dict_keys

_ANY = TypeAdapter(Any)


def to_jsonable_with_json_keys(val: Any, **kwargs: Any) -> Any:
    """Return `to_jsonable_python(val, **kwargs)` with dict keys written as `json.dumps` writes them.

    pydantic's JSON conversion turns a `None` key into `"None"`, while `json.dumps`,
    and so `canonical_json` and the digest, turn it into `"null"`. Models and
    dataclasses are expanded first, the way a request model dumped them, so their
    keys are converted too. This keeps the value that is sent equal to the value
    the digest saw, and keeps `{None: ..., "None": ...}` from collapsing into one key.
    """
    expanded = _ANY.dump_python(val, by_alias=True)
    if _has_non_string_dict_keys(expanded):
        expanded = _convert_dict_keys(expanded)
    return to_jsonable_python(expanded, **kwargs)


def _convert_dict_keys(val: Any) -> Any:
    if isinstance(val, dict):
        return {
            _json_dict_key(key): _convert_dict_keys(item) for key, item in val.items()
        }
    if isinstance(val, (list, tuple)):
        return [_convert_dict_keys(item) for item in val]
    return val


def _json_dict_key(key: Any) -> Any:
    # Other key types are left to to_jsonable_python.
    if key is None or isinstance(key, (bool, int, float)):
        return json.dumps(key)
    return key
