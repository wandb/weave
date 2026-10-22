from collections.abc import Mapping
from typing import Any, TypeAlias, cast

import pydantic

from weave.trace_server_bindings.http_utils import as_params
from weave.vendor.weave_server_sdk.types.call_stream_query_params import (
    Filter,
    SortBy,
)

# A calls filter is sent with every key, null when unset.
_CALLS_FILTER_KEYS = (
    "op_names",
    "input_refs",
    "output_refs",
    "parent_ids",
    "trace_ids",
    "call_ids",
    "thread_ids",
    "turn_ids",
    "trace_roots_only",
    "wb_user_ids",
    "wb_run_ids",
)


def cast_to_calls_filter(obj: Any) -> Filter:
    if isinstance(obj, (Mapping, pydantic.BaseModel)):
        return cast(Filter, {**dict.fromkeys(_CALLS_FILTER_KEYS), **as_params(obj)})

    raise TypeError(f"Unable to cast to CallsFilter: {obj}")


def cast_to_sort_by(obj: Any) -> SortBy:
    if isinstance(obj, (Mapping, pydantic.BaseModel)):
        return cast(SortBy, as_params(obj))

    raise TypeError(f"Unable to cast to SortBy: {obj}")


def cast_to_query(obj: Any) -> Mapping[str, Any]:
    """Return the query in wire form (`{"$expr": ...}`), which the server parses."""
    if isinstance(obj, (Mapping, pydantic.BaseModel)):
        return as_params(obj)

    raise TypeError(f"Unable to cast to Query: {obj}")


CallsFilterLike: TypeAlias = Filter | pydantic.BaseModel
SortByLike: TypeAlias = SortBy | pydantic.BaseModel
QueryLike: TypeAlias = Mapping[str, Any] | pydantic.BaseModel
