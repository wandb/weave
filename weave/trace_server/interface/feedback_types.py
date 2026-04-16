from typing import Any

from pydantic import BaseModel, Field

MAX_FEEDBACK_NOTE_LENGTH = 1024


class FeedbackPayloadReactionReq(BaseModel):
    emoji: str


class FeedbackPayloadNoteReq(BaseModel):
    note: str = Field(min_length=1, max_length=MAX_FEEDBACK_NOTE_LENGTH)


REACTION_FEEDBACK_TYPE = "wandb.reaction.1"
NOTE_FEEDBACK_TYPE = "wandb.note.1"

# Feedback types where multiple entries can exist per call per type.
# When filtering on these, we use groupArrayIf (collect all values) + has()
# instead of anyIf (pick one arbitrary value), which could miss matches.
MULTI_VALUE_FEEDBACK_TYPES = {REACTION_FEEDBACK_TYPE, NOTE_FEEDBACK_TYPE}

FEEDBACK_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    REACTION_FEEDBACK_TYPE: FeedbackPayloadReactionReq,
    NOTE_FEEDBACK_TYPE: FeedbackPayloadNoteReq,
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
