from typing import Optional

from pydantic import BaseModel

from weave.flow.obj import Object


class FeedbackType(BaseModel):
    display_name: str

    # If true, all unique creators will have their
    # own value for this feedback type. Otherwise,
    # by default, the value is shared and can be edited.
    unique_among_creators: bool = False


class HumanFeedback(Object):
    feedback_fields: list[FeedbackType]


class BinaryFeedback(FeedbackType):
    pass


class CategoricalFeedback(FeedbackType):
    options: list[str]


class NumericalFeedback(FeedbackType):
    min: Optional[float] = None
    max: Optional[float] = None


class TextFeedback(FeedbackType):
    max_length: Optional[int] = None
