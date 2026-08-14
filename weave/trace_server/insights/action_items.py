import datetime
from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from weave.trace_server.common_interface import BaseModelStrict


class ActionItemStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


class ActionItemSeverity(str, Enum):
    SEVERE = "SEVERE"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class ActionItem(BaseModelStrict):
    project_id: str
    cluster_run_id: str
    cluster_id: str
    run_window_end: datetime.datetime
    signature_type: Literal["intent", "failure"]
    id: str
    action_item_config_sha: str
    title: str
    description: str = ""
    evidence_trace_ids: list[str] = Field(default_factory=list)
    status: ActionItemStatus = ActionItemStatus.OPEN
    severity: ActionItemSeverity = ActionItemSeverity.MINOR
    inserted_at: datetime.datetime | None = None
    expire_at: datetime.datetime | None = None


class ActionItemsBatchUpsertReq(BaseModelStrict):
    items: list[ActionItem]


class ActionItemsBatchUpsertRes(BaseModelStrict):
    ids: list[str]


class ActionItemsQueryReq(BaseModelStrict):
    project_id: str
    cluster_run_id: str | None = None
    cluster_id: str | None = None
    statuses: list[ActionItemStatus] | None = None
    severities: list[ActionItemSeverity] | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class ActionItemsQueryRes(BaseModelStrict):
    items: list[ActionItem]


class ActionItemUpdateReq(BaseModelStrict):
    project_id: str
    cluster_run_id: str
    cluster_id: str
    id: str
    status: ActionItemStatus | None = None
    severity: ActionItemSeverity | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ActionItemUpdateReq":
        if self.status is None and self.severity is None:
            raise ValueError("status or severity is required")
        return self


class ActionItemUpdateRes(BaseModelStrict):
    item: ActionItem
