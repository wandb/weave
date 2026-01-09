"""Common interface types shared between trace server modules.

This module contains base classes and common types used by both
trace_server_interface.py and http_service_interface.py to avoid circular dependencies.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)


class BaseModelStrict(BaseModel):
    """Base model with strict validation that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")


class SortBy(BaseModelStrict):
    # Field should be a key of `CallSchema`. For dictionary fields
    # (`attributes`, `inputs`, `outputs`, `summary`), the field can be
    # dot-separated.
    field: str  # Consider changing this to _FieldSelect
    # Direction should be either 'asc' or 'desc'
    direction: Literal["asc", "desc"]


AnnotationState = Literal["unstarted", "in_progress", "completed", "skipped"]


class AnnotationQueueItemsFilter(BaseModel):
    """Simple filter for annotation queue items.

    Supports equality filtering on call metadata fields and IN filtering on annotation state.
    """

    call_id: str | None = Field(default=None, description="Filter by exact call ID")
    call_op_name: str | None = Field(
        default=None, description="Filter by exact operation name"
    )
    call_trace_id: str | None = Field(
        default=None, description="Filter by exact trace ID"
    )
    added_by: str | None = Field(
        default=None, description="Filter by W&B user ID who added the call"
    )
    annotation_states: list[AnnotationState] | None = Field(
        default=None,
        description="Filter by annotation states (unstarted, in_progress, completed, skipped)",
        examples=[["unstarted", "in_progress"]],
    )
