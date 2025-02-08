from __future__ import annotations

from typing import Annotated, Any, Union

from pydantic import BeforeValidator

import weave
from weave.flow.dataset import Dataset, short_str
from weave.scorers.base_scorer import Scorer, _validate_scorer_signature
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.table import Table
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
    elif callable(obj) and not is_op(obj):
        res = weave.op(obj)
    elif is_op(obj):
        res = as_op(obj)
    elif isinstance(obj, OpRef):
        res = obj.get()
    else:
        raise TypeError("Unable to cast to Scorer")

    _validate_scorer_signature(res)

    return res


def cast_to_table(obj: Any) -> Table:
    if isinstance(obj, Table):
        return obj

    if isinstance(obj, WeaveTable):
        return Table(rows=list(obj))

    raise TypeError("Unable to cast to Table")


def validate_table(table: Table) -> None:
    if len(table.rows) == 0:
        raise ValueError("Attempted to construct a Table with an empty list.")

    for row in table.rows:
        if not isinstance(row, dict):
            raise TypeError(
                "Attempted to construct a Table with a non-dict object. Found type: "
                + str(type(row))
                + " of row: "
                + short_str(row)
            )
        if len(row) == 0:
            raise ValueError("Attempted to construct a Table row with an empty dict.")


DatasetLike = Annotated[Dataset, BeforeValidator(cast_to_dataset)]
ScorerLike = Annotated[Union[Op, Scorer], BeforeValidator(cast_to_scorer)]
TableLike = Annotated[
    Table, BeforeValidator(cast_to_table), BeforeValidator(validate_table)
]
