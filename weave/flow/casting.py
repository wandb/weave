from __future__ import annotations

from typing import Annotated, Any, Union

from pydantic import BeforeValidator

import weave
from weave.flow.dataset import Dataset
from weave.flow.scorer import Scorer, _validate_scorer_signature
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import WeaveObject
from weave.trace_server.trace_server_interface import CallsFilter, Query, SortBy


def cast_to_dataset(obj: Any) -> Dataset:
    if isinstance(obj, Dataset):
        return obj

    if isinstance(obj, WeaveObject):
        return Dataset.from_obj(obj)

    if isinstance(obj, ObjectRef):
        return obj.get()

    if isinstance(obj, list):
        return Dataset(rows=obj)

    raise TypeError("Unable to cast to Dataset")


def cast_to_scorer(obj: Any) -> Scorer | Op:
    res: Scorer | Op
    if isinstance(obj, Scorer):
        res = obj
    elif isinstance(obj, type):
        raise TypeError(
            f"Scorer {obj.__name__} must be an instance, not a class. Did you instantiate?"
        )
    elif is_op(obj):
        res = as_op(obj)
    elif callable(obj):
        res = weave.op(obj)
    elif isinstance(obj, OpRef):
        res = obj.get()
    else:
        raise TypeError("Unable to cast to Scorer")

    _validate_scorer_signature(res)

    return res


def cast_to_calls_filter(obj: Any) -> CallsFilter:
    if isinstance(obj, CallsFilter):
        return obj

    if isinstance(obj, dict):
        return CallsFilter(**obj)

    if obj is None:
        return CallsFilter()

    raise TypeError("Unable to cast to CallsFilter")


def cast_to_sort_by(obj: Any) -> SortBy:
    if isinstance(obj, SortBy):
        return obj

    if isinstance(obj, dict):
        return SortBy(**obj)

    if isinstance(obj, str):
        # Handle simple string format like "started_at desc"
        parts = obj.split()
        if len(parts) == 2:
            field, direction = parts
            return SortBy(field=field, direction=direction)
        else:
            return SortBy(field=obj, direction="asc")

    raise TypeError(f"Unable to cast to SortBy: {obj}")


def cast_to_query(obj: Any) -> Query | None:
    if isinstance(obj, Query):
        return obj

    if isinstance(obj, dict):
        return Query(**obj)

    if obj is None:
        return None

    raise TypeError("Unable to cast to Query")


DatasetLike = Annotated[Dataset, BeforeValidator(cast_to_dataset)]
ScorerLike = Annotated[Union[Op, Scorer], BeforeValidator(cast_to_scorer)]

# calls query parameter types
CallsFilterLike = Annotated[CallsFilter, BeforeValidator(cast_to_calls_filter)]
SortByLike = Annotated[SortBy, BeforeValidator(cast_to_sort_by)]
QueryLike = Annotated[Query | None, BeforeValidator(cast_to_query)]
