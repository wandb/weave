import datetime
import json
from typing import Any
from zoneinfo import ZoneInfo

import emoji
from pydantic import ValidationError

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.emoji_util import detone_emojis
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.ids import generate_id
from weave.trace_server.interface.builtin_object_classes.annotation_spec import (
    AnnotationSpec,
)
from weave.trace_server.interface.feedback_types import (
    ANNOTATION_FEEDBACK_TYPE_PREFIX,
    FEEDBACK_PAYLOAD_SCHEMAS,
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    AnnotationPayloadSchema,
    RunnablePayloadSchema,
    feedback_type_is_annotation,
    feedback_type_is_runnable,
)
from weave.trace_server.orm import Column, Row, Table
from weave.trace_server.refs_internal_server_util import ensure_ref_is_valid
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
        Column("annotation_ref", "string", nullable=True),
        Column("runnable_ref", "string", nullable=True),
        Column("call_ref", "string", nullable=True),
        Column("trigger_ref", "string", nullable=True),
    ],
)


def process_feedback_payload(
    feedback_req: tsi.FeedbackCreateReq,
) -> dict[str, Any]:
    """Process feedback payload and return the processed payload.

    Args:
        feedback_req: The feedback create request.

    Returns:
        dict[str, Any]: The processed payload.

    Examples:
        >>> req = FeedbackCreateReq(project_id="test", feedback_type="custom", payload={"key": "value"})
        >>> processed = process_feedback_payload(req)
        >>> assert processed == {"key": "value"}
    """
    processed_payload = feedback_req.payload.copy()

    if feedback_req.feedback_type == "wandb.reaction.1":
        em = feedback_req.payload["emoji"]
        if emoji.emoji_count(em) != 1:
            raise InvalidRequest(
                "Value of emoji key in payload must be exactly one emoji"
            )
        processed_payload["alias"] = emoji.demojize(em)
        detoned = detone_emojis(em)
        processed_payload["detoned"] = detoned
        processed_payload["detoned_alias"] = emoji.demojize(detoned)

    # Validate payload size
    payload = json.dumps(processed_payload)
    if len(payload) > ch_settings.CLICKHOUSE_MAX_FEEDBACK_PAYLOAD_SIZE:
        raise InvalidRequest("Feedback payload too large")

    return processed_payload


def validate_feedback_create_req(
    req: tsi.FeedbackCreateReq, trace_server: tsi.TraceServerInterface
) -> None:
    payload_schema = FEEDBACK_PAYLOAD_SCHEMAS.get(req.feedback_type)
    if payload_schema:
        try:
            payload_schema(**req.payload)
        except ValidationError as e:
            raise InvalidRequest(
                f"Invalid payload for feedback_type {req.feedback_type}: {e}"
            ) from e

    # Validate the required fields for the feedback type.
    if feedback_type_is_annotation(req.feedback_type):
        if not req.feedback_type.startswith(ANNOTATION_FEEDBACK_TYPE_PREFIX + "."):
            raise InvalidRequest(
                f"Invalid annotation feedback type: {req.feedback_type}"
            )
        type_subname = req.feedback_type[len(ANNOTATION_FEEDBACK_TYPE_PREFIX) + 1 :]
        if not req.annotation_ref:
            raise InvalidRequest("annotation_ref is required for annotation feedback")
        annotation_ref = ensure_ref_is_valid(
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
            ) from e
    elif req.annotation_ref:
        raise InvalidRequest(
            "annotation_ref is not allowed for non-annotation feedback"
        )
    elif feedback_type_is_runnable(req.feedback_type):
        if not req.feedback_type.startswith(RUNNABLE_FEEDBACK_TYPE_PREFIX + "."):
            raise InvalidRequest(f"Invalid runnable feedback type: {req.feedback_type}")
        type_subname = req.feedback_type[len(RUNNABLE_FEEDBACK_TYPE_PREFIX) + 1 :]
        if not req.runnable_ref:
            raise InvalidRequest("runnable_ref is required for runnable feedback")
        runnable_ref = ensure_ref_is_valid(
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
            ) from e
    elif req.runnable_ref:
        raise InvalidRequest("runnable_ref is not allowed for non-runnable feedback")
    elif req.call_ref:
        raise InvalidRequest("call_ref is not allowed for non-runnable feedback")
    elif req.trigger_ref:
        raise InvalidRequest("trigger_ref is not allowed for non-runnable feedback")

    # Validate the ref formats (we could even query the DB to ensure they exist and are valid)
    if req.annotation_ref:
        parsed = ensure_ref_is_valid(req.annotation_ref, (ri.InternalObjectRef,))
        if parsed.project_id != req.project_id:
            raise InvalidRequest(
                f"Annotation ref {req.annotation_ref} does not match project id {req.project_id}"
            )

        # 2. Read the annotation spec
        data = trace_server.refs_read_batch(
            tsi.RefsReadBatchReq(refs=[req.annotation_ref])
        )
        if len(data.vals) == 0:
            raise InvalidRequest(f"Annotation ref {req.annotation_ref} not found")

        # 3. Validate the payload against the annotation spec
        value = req.payload["value"]
        spec = data.vals[0]
        is_valid = AnnotationSpec.model_validate(spec).value_is_valid(value)
        if not is_valid:
            raise InvalidRequest("Feedback payload does not match annotation spec")
    if req.runnable_ref:
        ensure_ref_is_valid(req.runnable_ref, (ri.InternalOpRef, ri.InternalObjectRef))
    if req.call_ref:
        ensure_ref_is_valid(req.call_ref, (ri.InternalCallRef,))
    if req.trigger_ref:
        ensure_ref_is_valid(req.trigger_ref, (ri.InternalObjectRef,))


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


def format_feedback_to_row(
    feedback_req: tsi.FeedbackCreateReq,
    processed_payload: dict[str, Any],
) -> Row:
    """Create a feedback row from a feedback request and processed payload.

    Args:
        feedback_req: The feedback create request.
        processed_payload: The processed payload from process_feedback_payload.

    Returns:
        Row: The feedback row ready for insertion.

    Examples:
        >>> req = FeedbackCreateReq(project_id="test", feedback_type="custom", payload={"key": "value"})
        >>> processed_payload = {"key": "value"}
        >>> row = format_feedback_to_row(req, processed_payload)
        >>> assert row["project_id"] == "test"
    """
    feedback_id = feedback_req.id or generate_id()
    created_at = datetime.datetime.now(ZoneInfo("UTC"))

    return {
        "id": feedback_id,
        "project_id": feedback_req.project_id,
        "weave_ref": feedback_req.weave_ref,
        "wb_user_id": feedback_req.wb_user_id,
        "creator": feedback_req.creator,
        "feedback_type": feedback_req.feedback_type,
        "payload": processed_payload,
        "created_at": created_at,
        "annotation_ref": feedback_req.annotation_ref,
        "runnable_ref": feedback_req.runnable_ref,
        "call_ref": feedback_req.call_ref,
        "trigger_ref": feedback_req.trigger_ref,
    }


def format_feedback_to_res(row: Row) -> tsi.FeedbackCreateRes:
    assert row["id"] is not None
    assert isinstance(row["id"], str)
    assert row["wb_user_id"] is not None
    assert isinstance(row["wb_user_id"], str)
    assert row["created_at"] is not None
    assert isinstance(row["created_at"], datetime.datetime)
    assert row["payload"] is not None
    assert isinstance(row["payload"], dict)

    return tsi.FeedbackCreateRes(
        id=row["id"],
        created_at=row["created_at"],
        wb_user_id=row["wb_user_id"],
        payload=row["payload"],
    )
