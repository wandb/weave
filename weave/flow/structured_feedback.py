from typing import Optional

from pydantic import BaseModel

from weave.flow.obj import Object


class FeedbackType(Object):
    name: str = None


class StructuredFeedback(Object):
    types: list[FeedbackType]


class BinaryFeedback(FeedbackType):
    type: str = "BinaryFeedback"


class NumericalFeedback(FeedbackType):
    type: str = "NumericalFeedback"

    min: float
    max: float


class TextFeedback(FeedbackType):
    type: str = "TextFeedback"


class CategoricalFeedback(FeedbackType):
    type: str = "CategoricalFeedback"

    options: list[str]
    multi_select: bool = False
    add_new_option: bool = False


if __name__ == "__main__":
    import weave

    api = weave.init("griffin_wb/trace-values")

    feedback = StructuredFeedback(
        types=[
            NumericalFeedback(min=0, max=5, name="Score"),
            CategoricalFeedback(
                name="Qualitative", options=["plain", "complex", "spicy"]
            ),
            BinaryFeedback(name="Viewed"),
            CategoricalFeedback(
                options=[],
                multi_select=True,
                add_new_option=True,
                name="Tags",
            ),
        ]
    )

    weave.publish(feedback, name="StructuredFeedback obj")
