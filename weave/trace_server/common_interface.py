"""Common interface types shared between trace server modules.

This module contains base classes and common types used by both
trace_server_interface.py and http_service_interface.py to avoid circular dependencies.
"""

import hashlib
import logging
import threading
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WB_USER_ID_DESCRIPTION = (
    "Do not set directly. Server will automatically populate this field."
)

logger = logging.getLogger(__name__)

# One warning per distinct model-and-fields message for the life of the process instead
# of one per request. The names are caller-controlled, so the memo is capped — far above
# the handful of distinct messages a fleet actually produces — and never evicted, since
# forgetting one would let it warn all over again.
MAX_WARNED_FIELD_SETS = 1024
_warned_field_sets: set[tuple[str, str]] = set()
_warned_field_sets_lock = threading.Lock()


def _warn_ignored_fields_once(model_name: str, extra_fields: set[str]) -> None:
    """Warn about a model's ignored fields the first time this warning would be sent."""
    # Built before anything else, so a payload the warning cannot render fails the same
    # way it did before this memo existed, whatever the log level. Sorted because equal
    # sets can still iterate in different orders, which would key the same fields twice.
    message = ", ".join(sorted(extra_fields))

    # Do not remember what the level suppressed; raising it later must still report.
    if not logger.isEnabledFor(logging.WARNING):
        return

    # Keyed on the message, so two field sets that read the same warn once. The names
    # are caller-controlled, hence the digest and surrogatepass: they can be long, and
    # a JSON body can carry a lone surrogate that UTF-8 alone cannot encode.
    digest = hashlib.sha256(message.encode("utf-8", "surrogatepass")).hexdigest()
    key = (model_name, digest)
    with _warned_field_sets_lock:
        if (
            key in _warned_field_sets
            or len(_warned_field_sets) >= MAX_WARNED_FIELD_SETS
        ):
            return
        _warned_field_sets.add(key)
        filled = len(_warned_field_sets) == MAX_WARNED_FIELD_SETS

    logger.warning(
        "Ignoring unexpected fields while validating %s: %s", model_name, message
    )
    if filled:
        logger.warning(
            "Reached %d distinct ignored-field sets; further sets will not be reported",
            MAX_WARNED_FIELD_SETS,
        )


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
        extra_fields = set(values) - known_fields
        if extra_fields:
            _warn_ignored_fields_once(cls.__name__, extra_fields)
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
