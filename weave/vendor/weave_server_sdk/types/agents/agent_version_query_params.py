# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["AgentVersionQueryParams", "SortBy"]


class AgentVersionQueryParams(TypedDict, total=False):
    agent_name: Required[str]

    project_id: Required[str]

    include_costs: bool

    limit: int

    offset: int

    sort_by: Optional[Iterable[SortBy]]


class SortBy(TypedDict, total=False):
    """Sort specification for agent query endpoints."""

    field: Required[str]

    direction: Literal["asc", "desc"]
