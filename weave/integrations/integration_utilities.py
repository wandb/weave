import hashlib
import re
from collections.abc import Iterable
from concurrent.futures import Future
from typing import Any, Union

from weave.trace.refs import OpRef, parse_uri
from weave.trace.weave_client import Call, CallsIter
from weave.trace_server.constants import MAX_OP_NAME_LENGTH


def make_pythonic_function_name(name: str) -> str:
    name = name.replace("<", "_").replace(">", "")

    valid_run_name = re.sub(r"[^a-zA-Z0-9 .\\-_]", "_", name)
    return valid_run_name


def truncate_op_name(name: str) -> str:
    if len(name) <= MAX_OP_NAME_LENGTH:
        return name

    trim_amount_needed = len(name) - MAX_OP_NAME_LENGTH
    parts = name.split(".")
    last_part = parts[-1]

    if len(last_part) <= trim_amount_needed:
        # In this case, the last part is shorter than the amount we need to trim.
        raise ValueError("Unable to create a valid run name from: " + name)

    last_part_len = len(last_part) - trim_amount_needed
    new_last_part = _uniquely_truncate_str(last_part, last_part_len)
    parts[-1] = new_last_part
    return ".".join(parts)


def _uniquely_truncate_str(s: str, max_len: int, max_hash_len: int = 4) -> str:
    if len(s) <= max_len:
        return s

    if max_len < 5:
        # In this case, we don't have enough "room" to add the hash
        return _truncate_string(s, max_len)

    hash_space = max_len - 4  # 1 character on either side of the hash + 2 split marker
    hash_len = min(max_hash_len, hash_space)

    max_len_to_keep = max_len - hash_len - 2  # 2 split marker
    start_len = max_len_to_keep // 2
    end_len = max_len_to_keep - start_len

    return (
        _truncate_string(s, start_len)
        + "_"
        + _hash_str(s, hash_len)
        + "_"
        + _truncate_string(s, end_len, True)
    )


def _truncate_string(s: str, max_len: int, from_start: bool = False) -> str:
    if len(s) <= max_len:
        return s

    if from_start:
        return s[-max_len:]
    else:
        return s[:max_len]


def _hash_str(s: str, hash_len: int) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:hash_len]


def flatten_calls(calls: Union[Iterable[Call], CallsIter], *, depth: int = 0) -> list:
    lst = []
    for call in calls:
        lst.append((call, depth))
        lst.extend(flatten_calls(call.children(), depth=depth + 1))
    return lst


def flattened_calls_to_names(flattened_calls: list) -> list:
    lst = []
    for call, depth in flattened_calls:
        ref = parse_uri(call.op_name)
        assert isinstance(ref, OpRef)
        lst.append((ref.name, depth))
    return lst


def op_name_from_ref(ref: str) -> str:
    return ref.split("/")[-1].split(":")[0]


def op_name_from_call(call: Call) -> str:
    if isinstance(op_name := call._op_name, Future):
        op_name = op_name.result()
    return op_name_from_ref(op_name)


def filter_body(r: Any) -> Any:
    r.body = ""
    return r


def _make_string_of_length(n: int) -> str:
    return "a" * n


def _truncated_str(tail_len: int, total_len: int) -> tuple:
    name = (
        _make_string_of_length(total_len - tail_len - 1)
        + "."
        + _make_string_of_length(tail_len)
    )
    return name, truncate_op_name(name)
