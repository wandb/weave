from typing import Annotated, Any

import pydantic

from weave.trace_server.trace_server_interface import CallsFilter, Query, SortBy


def cast_to_calls_filter(obj: Any) -> CallsFilter:
    if isinstance(obj, CallsFilter):
        return obj

    if isinstance(obj, dict):
        return CallsFilter(**obj)

    raise TypeError(f"Unable to cast to CallsFilter: {obj}")


def cast_to_sort_by(obj: Any) -> SortBy:
    if isinstance(obj, SortBy):
        return obj

    if isinstance(obj, dict):
        return SortBy(**obj)

    raise TypeError(f"Unable to cast to SortBy: {obj}")


def cast_to_query(obj: Any) -> Query:
    if isinstance(obj, Query):
        return obj

    if isinstance(obj, dict):
        return Query(**obj)

    raise TypeError(f"Unable to cast to Query: {obj}")


CallsFilterLike = Annotated[CallsFilter, pydantic.BeforeValidator(cast_to_calls_filter)]
SortByLike = Annotated[SortBy, pydantic.BeforeValidator(cast_to_sort_by)]
QueryLike = Annotated[Query, pydantic.BeforeValidator(cast_to_query)]
