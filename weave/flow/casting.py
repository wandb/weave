from __future__ import annotations

from typing import Annotated, Any, TypedDict, Union

from pydantic import BeforeValidator
from typing_extensions import NotRequired

import weave
from weave.flow.dataset import Dataset
from weave.scorers.base_scorer import Scorer, _validate_scorer_signature
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import Call


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


class ModelMetadata(TypedDict):
    """Metadata about a model run."""

    latency: float
    call: NotRequired[Call]


class EvaluationRow(TypedDict):
    """Defines an explicit schema for an evaluation row."""

    inputs: Any
    output: NotRequired[Any]
    scores: NotRequired[dict[str, Any]]
    metadata: NotRequired[ModelMetadata]  # Replacing model_call with metadata


def normalize_eval_row(row: dict) -> EvaluationRow:
    """
    Normalize an input row to conform to the EvaluationRow schema.
    If the row already contains an "inputs" key, assume it is largely normalized,
    and add any missing optional fields.
    Otherwise, assume the entire row represents the input.
    """
    # If the row already has an "inputs" key, rebuild the dict ensuring only expected keys are present.
    if "inputs" in row:
        normalized_row: EvaluationRow = {"inputs": row["inputs"]}
        if "output" in row:
            normalized_row["output"] = row["output"]
        if "scores" in row:
            normalized_row["scores"] = row["scores"]
        if "metadata" in row:
            normalized_row["metadata"] = row["metadata"]
        return normalized_row
    # Otherwise, treat the entire row as the input.
    return {"inputs": row}


DatasetLike = Annotated[Dataset, BeforeValidator(cast_to_dataset)]
ScorerLike = Annotated[Union[Op, Scorer], BeforeValidator(cast_to_scorer)]
