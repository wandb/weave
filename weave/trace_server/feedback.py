from typing import Any

from pydantic import BaseModel, ValidationError

from . import trace_server_interface as tsi
from .errors import InvalidRequest
from .orm import Column, Table

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


MESSAGE_INVALID_PURGE = "Can only purge feedback by specifying one or more ids"


def validate_dict_one_key(d: dict, key: str, typ: type) -> Any:
    if not isinstance(d, dict):
        raise InvalidRequest(f"Expected a dictionary, got {d}")
    keys = list(d.keys())
    if len(keys) != 1:
        raise InvalidRequest(f"Expected a dictionary with one key, got {d}")
    if keys[0] != key:
        raise InvalidRequest(f"Expected key {key}, got {keys[0]}")
    val = d[key]
    if not isinstance(val, typ):
        raise InvalidRequest(f"Expected value of type {typ}, got {type(val)}")
    return val


def validate_feedback_purge_req_one(value: Any) -> None:
    tup = validate_dict_one_key(value, "eq_", tuple)
    if len(tup) != 2:
        raise InvalidRequest(MESSAGE_INVALID_PURGE)
    get_field = validate_dict_one_key(tup[0], "get_field_", str)
    if get_field != "id":
        raise InvalidRequest(MESSAGE_INVALID_PURGE)
    literal = validate_dict_one_key(tup[1], "literal_", str)
    if not isinstance(literal, str):
        raise InvalidRequest(MESSAGE_INVALID_PURGE)


def validate_feedback_purge_req_multiple(value: Any) -> None:
    if not isinstance(value, list):
        raise InvalidRequest(MESSAGE_INVALID_PURGE)
    for item in value:
        validate_feedback_purge_req_one(item)


def validate_feedback_purge_req(req: tsi.FeedbackPurgeReq) -> None:
    """For safety, we currently only allow purging by feedback id."""
    expr = req.query.expr_.model_dump()
    keys = list(expr.keys())
    if len(keys) != 1:
        raise InvalidRequest(MESSAGE_INVALID_PURGE)
    if keys[0] == "eq_":
        validate_feedback_purge_req_one(expr)
    elif keys[0] == "or_":
        validate_feedback_purge_req_multiple(expr["or_"])
    else:
        raise InvalidRequest(MESSAGE_INVALID_PURGE)
