from __future__ import annotations

from typing import Annotated, Any

from pydantic import BeforeValidator

import weave
from weave.dataset.dataset import Dataset
from weave.flow.scorer import Scorer, _validate_scorer_signature
from weave.trace.isinstance import weave_isinstance
from weave.trace.op import as_op, is_op
from weave.trace.op_protocol import Op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import WeaveObject


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
    elif weave_isinstance(obj, Scorer):
        res = Scorer.from_obj(obj)
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
ScorerLike = Annotated[Op | Scorer, BeforeValidator(cast_to_scorer)]
