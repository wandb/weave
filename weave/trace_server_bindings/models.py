from typing import Annotated, Literal

from pydantic import BaseModel, Field

from weave.trace_server import trace_server_interface as tsi


class StartBatchItem(BaseModel):
    mode: Literal["start"] = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: Literal["end"] = "end"
    req: tsi.CallEndReq


class CompleteBatchItem(BaseModel):
    """A complete call ready to be sent to calls_complete endpoint."""

    mode: Literal["complete"] = "complete"
    req: tsi.CompletedCallSchemaForInsert


class Batch(BaseModel):
    # Discriminated: untagged, each item is tried against the wrong member and warns.
    batch: list[Annotated[StartBatchItem | EndBatchItem, Field(discriminator="mode")]]


class EntityProjectInfo(BaseModel):
    """Extracted entity and project information from a project_id."""

    entity: str
    project: str
    project_id: str
