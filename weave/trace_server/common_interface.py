"""Common interface types shared between trace server modules.

This module contains base classes and common types used by both
trace_server_interface.py and http_service_interface.py to avoid circular dependencies.
"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)

logger = logging.getLogger(__name__)


class BaseModelStrict(BaseModel):
    """API model that tolerates and reports unknown additive fields."""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def warn_on_extra_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        known_fields = set(cls.model_fields)
        known_fields.update(
            field.alias
            for field in cls.model_fields.values()
            if field.alias is not None
        )
        extra_fields = sorted(set(values) - known_fields)
        if extra_fields:
            logger.warning(
                "Ignoring unexpected fields while validating %s: %s",
                cls.__name__,
                ", ".join(extra_fields),
            )
        return values


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

    id: str | None = Field(default=None, description="Filter by exact queue item ID")
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
