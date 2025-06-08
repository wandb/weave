from collections.abc import Iterable
from typing import Annotated, Any

import pydantic

from weave.trace.isinstance import weave_isinstance
from weave.trace.table import Table
from weave.trace.vals import WeaveTable
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


def cast_to_table(obj: Any) -> Table | WeaveTable:
    if isinstance(obj, Table):
        return obj
    if weave_isinstance(obj, WeaveTable):
        return obj

    # Try to create a Table from iterable of dicts
    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        rows = list(obj)
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError(
                    f"Unable to cast to Table: all items must be dicts. Found type: {type(row)}"
                )
            if len(row) == 0:
                raise ValueError("Unable to cast to Table: dict cannot be empty.")
            if not all(isinstance(k, str) for k in row.keys()):
                raise TypeError(
                    f"Unable to cast to Table: all dicts must have string keys. Found type: {type(row)}"
                )
        return Table(rows)

    raise TypeError("Unable to cast to Table")


CallsFilterLike = Annotated[CallsFilter, pydantic.BeforeValidator(cast_to_calls_filter)]
SortByLike = Annotated[SortBy, pydantic.BeforeValidator(cast_to_sort_by)]
QueryLike = Annotated[Query, pydantic.BeforeValidator(cast_to_query)]
TableLike = Annotated[
    Table | WeaveTable | list[dict],
    pydantic.BeforeValidator(cast_to_table),
]
