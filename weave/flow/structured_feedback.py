from typing import Optional

from pydantic import BaseModel

from weave.flow.obj import Object


class FeedbackType(BaseModel):
    editable: bool = True


class StructuredFeedback(Object):
    types: list[dict]


class BinaryFeedback(FeedbackType):
    name: Optional[str] = None
    type: str = "BinaryFeedback"


class RangeFeedback(FeedbackType):
    name: Optional[str] = None
    type: str = "RangeFeedback"

    min: float
    max: float


class CategoricalFeedback(FeedbackType):
    name: Optional[str] = None
    type: str = "CategoricalFeedback"

    options: list[str]
    multi_select: bool = False
    add_new_option: bool = False


if __name__ == "__main__":
    import weave

    api = weave.init("griffin_wb/trace-values")

    feedback = StructuredFeedback(
        types=[
            RangeFeedback(min=0, max=1).model_dump(),
            RangeFeedback(min=0, max=10, name="score-val").model_dump(),
            CategoricalFeedback(
                options=["option a", "option b", "option c"]
            ).model_dump(),
            BinaryFeedback(name="binary-feedback", editable=False).model_dump(),
            CategoricalFeedback(
                options=[],
                multi_select=True,
                add_new_option=True,
                name="Tags",
            ).model_dump(),
        ]
    )

    weave.publish(feedback, name="StructuredFeedback obj")
