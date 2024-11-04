from typing import Any, Optional, Tuple, Type, TypeVar, Union, overload

from pydantic import BaseModel, ValidationError

from weave.trace_server import refs_internal as ri
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


T = TypeVar(
    "T", ri.InternalObjectRef, ri.InternalTableRef, ri.InternalCallRef, ri.InternalOpRef
)


@overload
def _ensure_ref_is_valid(
    ref: str, expected_type: None = None
) -> Union[ri.InternalObjectRef, ri.InternalTableRef, ri.InternalCallRef]: ...


@overload
def _ensure_ref_is_valid(
    ref: str,
    expected_type: Tuple[Type[T], ...],
) -> T: ...


def _ensure_ref_is_valid(
    ref: str, expected_type: Optional[Tuple[Type, ...]] = None
) -> Union[ri.InternalObjectRef, ri.InternalTableRef, ri.InternalCallRef]:
    """Validates and parses an internal URI reference.

    Args:
        ref: The reference string to validate
        expected_type: Optional tuple of expected reference types

    Returns:
        The parsed internal reference object

    Raises:
        InvalidRequest: If the reference is invalid or doesn't match expected_type
    """
    try:
        parsed_ref = ri.parse_internal_uri(ref)
    except ValueError as e:
        raise InvalidRequest(f"Invalid ref: {ref}, {e}")
    if expected_type and not isinstance(parsed_ref, expected_type):
        raise InvalidRequest(
            f"Invalid ref: {ref}, expected {(t.__name__ for t in expected_type)}"
        )
    return parsed_ref


def validate_feedback_create_req(req: tsi.FeedbackCreateReq) -> None:
    payload_schema = FEEDBACK_PAYLOAD_SCHEMAS.get(req.feedback_type)
    if payload_schema:
        try:
            payload_schema(**req.payload)
        except ValidationError as e:
            raise InvalidRequest(
                f"Invalid payload for feedback_type {req.feedback_type}: {e}"
            )

    # Validate the required fields for the feedback type.
    is_annotation = req.feedback_type.startswith(ANNOTATION_FEEDBACK_TYPE_PREFIX)
    is_runnable = req.feedback_type.startswith(RUNNABLE_FEEDBACK_TYPE_PREFIX)
    if is_annotation:
        if not req.feedback_type.startswith(ANNOTATION_FEEDBACK_TYPE_PREFIX + "."):
            raise InvalidRequest(
                f"Invalid annotation feedback type: {req.feedback_type}"
            )
        type_subname = req.feedback_type[len(ANNOTATION_FEEDBACK_TYPE_PREFIX) + 1 :]
        if not req.annotation_ref:
            raise InvalidRequest("annotation_ref is required for annotation feedback")
        annotation_ref = _ensure_ref_is_valid(
            req.annotation_ref, (ri.InternalObjectRef,)
        )
        if annotation_ref.name != type_subname:
            raise InvalidRequest(
                f"annotation_ref must point to an object with name {type_subname}"
            )
        try:
            AnnotationPayloadSchema.model_validate(req.payload)
        except ValidationError as e:
            raise InvalidRequest(
                f"Invalid payload for feedback_type {req.feedback_type}: {e}"
            )
    elif req.annotation_ref:
        raise InvalidRequest(
            "annotation_ref is not allowed for non-annotation feedback"
        )
    elif is_runnable:
        if not req.feedback_type.startswith(RUNNABLE_FEEDBACK_TYPE_PREFIX + "."):
            raise InvalidRequest(f"Invalid runnable feedback type: {req.feedback_type}")
        type_subname = req.feedback_type[len(RUNNABLE_FEEDBACK_TYPE_PREFIX) + 1 :]
        if not req.runnable_ref:
            raise InvalidRequest("runnable_ref is required for runnable feedback")
        runnable_ref = _ensure_ref_is_valid(
            req.runnable_ref, (ri.InternalOpRef, ri.InternalObjectRef)
        )
        if runnable_ref.name != type_subname:
            raise InvalidRequest(
                f"runnable_ref must point to an object with name {type_subname}"
            )
        if isinstance(runnable_ref, ri.InternalOpRef) and not req.call_ref:
            raise InvalidRequest("call_ref is required for runnable feedback on ops")
        try:
            RunnablePayloadSchema.model_validate(req.payload)
        except ValidationError as e:
            raise InvalidRequest(
                f"Invalid payload for feedback_type {req.feedback_type}: {e}"
            )
    elif req.runnable_ref:
        raise InvalidRequest("runnable_ref is not allowed for non-runnable feedback")
    elif req.call_ref:
        raise InvalidRequest("call_ref is not allowed for non-runnable feedback")
    elif req.trigger_ref:
        raise InvalidRequest("trigger_ref is not allowed for non-runnable feedback")

    # Validate the ref formats (we could even query the DB to ensure they exist and are valid)
    if req.annotation_ref:
        _ensure_ref_is_valid(req.annotation_ref, (ri.InternalObjectRef,))
    if req.runnable_ref:
        _ensure_ref_is_valid(req.runnable_ref, (ri.InternalOpRef, ri.InternalObjectRef))
    if req.call_ref:
        _ensure_ref_is_valid(req.call_ref, (ri.InternalCallRef,))
    if req.trigger_ref:
        _ensure_ref_is_valid(req.trigger_ref, (ri.InternalObjectRef,))


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
