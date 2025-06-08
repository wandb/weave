from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Any, Union

from pydantic import BeforeValidator

import weave
from weave.flow.dataset import Dataset
from weave.flow.scorer import Scorer, _validate_scorer_signature
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.table import Table
from weave.trace.vals import WeaveObject, WeaveTable


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


DatasetLike = Annotated[Dataset, BeforeValidator(cast_to_dataset)]
ScorerLike = Annotated[Union[Op, Scorer], BeforeValidator(cast_to_scorer)]
