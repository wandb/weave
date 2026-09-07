# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["DatasetSourceLinkParams", "Link", "LinkSource"]


class DatasetSourceLinkParams(TypedDict, total=False):
    dataset_digest: Required[str]

    dataset_object_id: Required[str]

    links: Required[Iterable[Link]]

    project_id: Required[str]

    include_created_status: bool

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""


class LinkSource(TypedDict, total=False):
    """
    Reference to a provenance source (a call, an agent span, or a
    conversation).
    """

    source_id: Required[str]

    source_kind: Required[Literal["call", "span", "conversation"]]

    source_trace_id: Required[str]


class Link(TypedDict, total=False):
    """A single dataset row and the sources to link to it."""

    row_digest: Required[str]

    sources: Required[Iterable[LinkSource]]

    link_metadata: Optional[Dict[str, object]]
