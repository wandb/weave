from pydantic import BaseModel, ValidationError

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.orm import Column, Table
from weave.trace_server.validation import (
    validate_purge_req_multiple,
    validate_purge_req_one,
)

TABLE_FEEDBACK = Table(
    "feedback",
    [
        Column("id", "string"),
        Column("project_id", "string"),
        Column("weave_ref", "string"),
        Column("wb_user_id", "string"),
        Column("creator", "string", nullable=True),
        Column("created_at", "datetime"),
        Column("feedback_type", "string"),
        Column("payload", "json", db_name="payload_dump"),
    ],
)


FEEDBACK_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "wandb.reaction.1": tsi.FeedbackPayloadReactionReq,
    "wandb.note.1": tsi.FeedbackPayloadNoteReq,
}


def validate_feedback_create_req(req: tsi.FeedbackCreateReq) -> None:
    payload_schema = FEEDBACK_PAYLOAD_SCHEMAS.get(req.feedback_type)
    if payload_schema:
        try:
            payload_schema(**req.payload)
        except ValidationError as e:
            raise InvalidRequest(
                f"Invalid payload for feedback_type {req.feedback_type}: {e}"
            )


MESSAGE_INVALID_FEEDBACK_PURGE = (
    "Can only purge feedback by specifying one or more feedback ids"
)


def validate_feedback_purge_req(req: tsi.FeedbackPurgeReq) -> None:
    """For safety, we currently only allow purging by feedback id."""
    expr = req.query.expr_.model_dump()
    keys = list(expr.keys())
    if len(keys) != 1:
        raise InvalidRequest(MESSAGE_INVALID_FEEDBACK_PURGE)
    if keys[0] == "eq_":
        validate_purge_req_one(expr, MESSAGE_INVALID_FEEDBACK_PURGE)
    elif keys[0] == "or_":
        validate_purge_req_multiple(expr["or_"], MESSAGE_INVALID_FEEDBACK_PURGE)
    else:
        raise InvalidRequest(MESSAGE_INVALID_FEEDBACK_PURGE)
