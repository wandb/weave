from typing import Any

from pydantic import BaseModel, Field


class FeedbackPayloadReactionReq(BaseModel):
    emoji: str


class FeedbackPayloadNoteReq(BaseModel):
    note: str = Field(min_length=1, max_length=1024)


FEEDBACK_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "wandb.reaction.1": FeedbackPayloadReactionReq,
    "wandb.note.1": FeedbackPayloadNoteReq,
}

ANNOTATION_FEEDBACK_TYPE_PREFIX = "wandb.annotation"
RUNNABLE_FEEDBACK_TYPE_PREFIX = "wandb.runnable"


# Making the decision to use `value` & `payload` as nested keys so that
# we can:
# 1. Add more fields in the future without breaking changes
# 2. Support primitive values for annotation feedback that still schema
class AnnotationPayloadSchema(BaseModel):
    value: Any


class RunnablePayloadSchema(BaseModel):
    output: Any


def feedback_type_is_annotation(feedback_type: str) -> bool:
    return feedback_type.startswith(ANNOTATION_FEEDBACK_TYPE_PREFIX)


def feedback_type_is_runnable(feedback_type: str) -> bool:
    return feedback_type.startswith(RUNNABLE_FEEDBACK_TYPE_PREFIX)


def runnable_feedback_selector(name: str) -> str:
    return f"feedback.[{RUNNABLE_FEEDBACK_TYPE_PREFIX}.{name}]"


def runnable_feedback_output_selector(name: str) -> str:
    return f"{runnable_feedback_selector(name)}.payload.output"


def runnable_feedback_runnable_ref_selector(name: str) -> str:
    return f"{runnable_feedback_selector(name)}.runnable_ref"
