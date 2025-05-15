from __future__ import annotations

from typing import Annotated, Any, Union

from pydantic import BeforeValidator

import weave
from weave.flow.dataset import Dataset
from weave.flow.scorer import Scorer, _validate_scorer_signature
from weave.trace.op import Op, as_op, is_op
from weave.trace.refs import ObjectRef, OpRef
from weave.trace.vals import WeaveObject
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModelDefaultParams,
    Message,
)


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


def cast_to_message_list(obj: Any) -> list[Message]:
    if isinstance(obj, Message):
        return [obj]
    elif isinstance(obj, dict):
        return [Message.model_validate(obj)]
    elif isinstance(obj, list):
        return [cast_to_message(item) for item in obj]
    raise TypeError("Unable to cast to Message")


def cast_to_message(obj: Any) -> Message:
    if isinstance(obj, Message):
        return obj
    elif isinstance(obj, dict):
        return Message.model_validate(obj)
    elif isinstance(obj, str):
        return Message(content=obj, role="user")
    raise TypeError("Unable to cast to Message")


def cast_to_llm_structured_model_params(
    obj: Any,
) -> LLMStructuredCompletionModelDefaultParams:
    if isinstance(obj, LLMStructuredCompletionModelDefaultParams):
        return obj
    elif isinstance(obj, dict):
        return LLMStructuredCompletionModelDefaultParams.model_validate(obj)
    raise TypeError("Unable to cast to LLMStructuredCompletionModelDefaultParams")


DatasetLike = Annotated[Dataset, BeforeValidator(cast_to_dataset)]
ScorerLike = Annotated[Union[Op, Scorer], BeforeValidator(cast_to_scorer)]
MessageListLike = Annotated[list[Message], BeforeValidator(cast_to_message_list)]
MessageLike = Annotated[Message, BeforeValidator(cast_to_message)]
LLMStructuredModelParamsLike = Annotated[
    LLMStructuredCompletionModelDefaultParams,
    BeforeValidator(cast_to_llm_structured_model_params),
]
