# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["CallUsageParams"]


class CallUsageParams(TypedDict, total=False):
    call_ids: Required[SequenceNotStr[str]]
    """Root call IDs to aggregate. Each result key corresponds to one input call ID."""

    project_id: Required[str]

    include_costs: bool
    """If true, include cost calculations in the usage."""

    limit: int
    """Maximum number of calls to process across all traces.

    Acts as a safety limit to prevent unbounded memory usage.
    """
