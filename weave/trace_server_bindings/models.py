from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from weave.shared import trace_server_interface as tsi
from weave.vendor.weave_server_sdk.types import (
    CallEndParams,
    CallStartParams,
    v2_call_complete_params,
)


@dataclass(kw_only=True)
class StartBatchItem:
    mode: Literal["start"] = "start"
    req: CallStartParams | tsi.CallStartReq


@dataclass(kw_only=True)
class EndBatchItem:
    mode: Literal["end"] = "end"
    req: CallEndParams | tsi.CallEndReq


@dataclass(kw_only=True)
class CompleteBatchItem:
    """A complete call ready to be sent to calls_complete endpoint."""

    mode: Literal["complete"] = "complete"
    req: v2_call_complete_params.Batch | tsi.CompletedCallSchemaForInsert


class EntityProjectInfo(BaseModel):
    """Extracted entity and project information from a project_id."""

    entity: str
    project: str
    project_id: str
