from __future__ import annotations

from typing import Annotated, Any, Union

from pydantic import BeforeValidator

import weave
from weave.flow.dataset import Dataset
from weave.flow.scorer import Scorer, _validate_scorer_signature
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import WeaveObject, WeaveTable


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


def _short_str(obj: Any, limit: int = 25) -> str:
    str_val = str(obj)
    if len(str_val) > limit:
        return str_val[:limit] + "..."
    return str_val


def cast_to_table(rows: Any) -> weave.Table | WeaveTable:
    if weave_isinstance(rows, WeaveTable):
        return rows
    if not isinstance(rows, weave.Table):
        table_ref = getattr(rows, "table_ref", None)
        rows = weave.Table(rows)
        if table_ref:
            rows.table_ref = table_ref
    if len(rows.rows) == 0:
        raise ValueError("Attempted to construct a Dataset with an empty list.")
    for row in rows.rows:
        if not isinstance(row, dict):
            raise TypeError(
                "Attempted to construct a Dataset with a non-dict object. Found type: "
                + str(type(row))
                + " of row: "
                + _short_str(row)
            )
        if len(row) == 0:
            raise ValueError("Attempted to construct a Dataset row with an empty dict.")

    return rows


DatasetLike = Annotated[Dataset, BeforeValidator(cast_to_dataset)]
ScorerLike = Annotated[Union[Op, Scorer], BeforeValidator(cast_to_scorer)]
TableLike = Annotated[Union[weave.Table, WeaveTable], BeforeValidator(cast_to_table)]
