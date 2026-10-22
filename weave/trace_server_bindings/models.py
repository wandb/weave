from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from weave.vendor.weave_server_sdk.types import (
    CallEndParams,
    CallStartParams,
    v2_call_complete_params,
)
from weave.vendor.weave_server_sdk.types.call_read_response import Call


@dataclass(kw_only=True)
class StartBatchItem:
    mode: Literal["start"] = "start"
    req: CallStartParams


@dataclass(kw_only=True)
class EndBatchItem:
    mode: Literal["end"] = "end"
    req: CallEndParams


@dataclass(kw_only=True)
class CompleteBatchItem:
    """A complete call ready to be sent to calls_complete endpoint."""

    mode: Literal["complete"] = "complete"
    req: v2_call_complete_params.Batch


@dataclass(kw_only=True)
class CallsQueryRes:
    """The response of `calls_query`, which the generated client has no type for."""

    calls: list[Call]


@dataclass
class DatasetSourcesLinkDeleteEntry:
    """Whether one link was deleted; False if it was already deleted."""

    link_id: str
    deleted: bool


@dataclass
class DatasetSourcesLinkDeleteRes:
    """The `dataset_sources_link_delete` response, which the generated client lacks."""

    entries: list[DatasetSourcesLinkDeleteEntry]


@dataclass
class EnsureProjectExistsRes:
    """What `ensure_project_exists` returns: it calls W&B, not a trace server route."""

    project_name: str


@dataclass
class FileContentReadRes:
    """A file's content; the generated client has no model for a binary body."""

    content: bytes
