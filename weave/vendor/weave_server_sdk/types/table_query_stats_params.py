# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["TableQueryStatsParams"]


class TableQueryStatsParams(TypedDict, total=False):
    digest: Required[str]
    """The digest of the table to query"""

    project_id: Required[str]
    """The ID of the project"""
