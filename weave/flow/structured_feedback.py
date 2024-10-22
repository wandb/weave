from typing import Optional

from pydantic import BaseModel

from weave.flow.obj import Object


class FeedbackType(BaseModel):
    pass


class StructuredFeedback(Object):
    types: list[dict]


class RangeFeedback(FeedbackType):
    name: Optional[str] = None
    type: str = "RangeFeedback"

    min: float
    max: float


class CategoricalFeedback(FeedbackType):
    name: Optional[str] = None
    type: str = "CategoricalFeedback"

    options: list[str]


if __name__ == "__main__":
    import weave

    api = weave.init("griffin_wb/prod-evals-aug")

    existing_evaluations = api.get_calls(
        filter={"call_ids": ["019268dc-cdf8-7dc2-8719-34f0a7492263"]}
    )
    print(existing_evaluations)

    eval_1 = existing_evaluations[0]

    feedback = StructuredFeedback(
        types=[
            RangeFeedback(min=0, max=100).model_dump(),
            RangeFeedback(min=0, max=10, name="score-val").model_dump(),
            CategoricalFeedback(
                options=["option a", "option b", "option c"]
            ).model_dump(),
        ]
    )

    weave.publish(feedback, name="StructuredFeedback obj")
