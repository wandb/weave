# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["DatasetSourceSourceDatasetsQueryParams", "Source"]


class DatasetSourceSourceDatasetsQueryParams(TypedDict, total=False):
    project_id: Required[str]

    sources: Required[Iterable[Source]]

    include_deleted: bool

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""


class Source(TypedDict, total=False):
    """
    Reference to a provenance source (a call, an agent span, or a
    conversation).
    """

    source_id: Required[str]

    source_kind: Required[Literal["call", "span", "conversation"]]

    source_trace_id: Required[str]
