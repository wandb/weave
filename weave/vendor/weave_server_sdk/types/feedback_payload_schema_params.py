# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Optional
from datetime import datetime
from typing_extensions import Required, Annotated, TypedDict

from .._utils import PropertyInfo

__all__ = ["FeedbackPayloadSchemaParams"]


class FeedbackPayloadSchemaParams(TypedDict, total=False):
    project_id: Required[str]

    start: Required[Annotated[Union[str, datetime], PropertyInfo(format="iso8601")]]
    """Inclusive start time (UTC, ISO 8601)."""

    end: Annotated[Union[str, datetime, None], PropertyInfo(format="iso8601")]
    """Exclusive end time (UTC, ISO 8601). Defaults to now if omitted."""

    feedback_type: Optional[str]
    """Filter by feedback_type."""

    sample_limit: int
    """Max distinct trigger_refs to sample when discovering the payload schema.

    Each distinct trigger_ref (monitor/source) typically has a fixed payload
    structure, so sampling one payload per ref is usually enough to see the full
    schema. 2 000 covers virtually all real-world projects while keeping the query
    fast; the hard cap of 5 000 prevents runaway scans.
    """

    trigger_ref: Optional[str]
    """Filter by trigger_ref (exact or prefix match for all-versions)."""
