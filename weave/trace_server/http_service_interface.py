"""HTTP service interface models for trace server REST API.

This module contains Pydantic models used in HTTP request bodies for REST endpoints.
These models typically exclude path parameters (like queue_id, project_id) which are
included in the URL path, whereas the full request models in trace_server_interface.py
include all parameters for internal use.
"""

from pydantic import Field

from weave.trace_server.common_interface import (
    WB_USER_ID_DESCRIPTION,
    AnnotationQueueItemsFilter,
    BaseModelStrict,
    SortBy,
)


class AnnotationQueueAddCallsBody(BaseModelStrict):
    """Request body for adding calls to an annotation queue (queue_id comes from path)."""

    project_id: str = Field(examples=["entity/project"])
    call_ids: list[str] = Field(examples=[["call-1", "call-2", "call-3"]])
    display_fields: list[str] = Field(
        examples=[["input.prompt", "output.text"]],
        description="JSON paths to display to annotators",
    )
    wb_user_id: str | None = Field(None, description=WB_USER_ID_DESCRIPTION)


class AnnotationQueueItemsQueryBody(BaseModelStrict):
    """Request body for querying items in an annotation queue (queue_id comes from path)."""

    project_id: str = Field(examples=["entity/project"])
    filter: AnnotationQueueItemsFilter | None = Field(
        default=None,
        description="Filter queue items by call metadata and annotation state",
    )
    sort_by: list[SortBy] | None = Field(
        default=None,
        description="Sort by multiple fields (e.g., created_at, updated_at)",
    )
    limit: int | None = Field(default=None, examples=[50])
    offset: int | None = Field(default=None, examples=[0])
    include_position: bool = Field(
        default=False,
        description="Include position_in_queue field (1-based index in full queue)",
    )
