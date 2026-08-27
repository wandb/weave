# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal, Required, TypedDict

__all__ = ["AgentQueryParams", "Filters", "SortBy"]


class AgentQueryParams(TypedDict, total=False):
    project_id: Required[str]

    filters: Optional[Filters]
    """Optional filters for querying agents."""

    include_costs: bool

    limit: int

    offset: int

    sort_by: Optional[Iterable[SortBy]]


class Filters(TypedDict, total=False):
    """Optional filters for querying agents."""

    agent_name: Optional[str]


class SortBy(TypedDict, total=False):
    """Sort specification for agent query endpoints."""

    field: Required[str]

    direction: Literal["asc", "desc"]
