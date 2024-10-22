from pydantic import BaseModel

from weave.trace_server.interface.feedback_types.feedback_type import FeedbackType

ACTION_FEEDBACK_TYPE_NAME = "wandb.action.1"


class ActionFeedback(BaseModel):
    name: str
    action_ref: str
    results: dict


action_feedback_type = FeedbackType(
    name=ACTION_FEEDBACK_TYPE_NAME,
    payload_spec=ActionFeedback,
)
