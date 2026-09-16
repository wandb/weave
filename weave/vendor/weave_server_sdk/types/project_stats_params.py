# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["ProjectStatsParams"]


class ProjectStatsParams(TypedDict, total=False):
    project_id: Required[str]

    include_file_storage_size: Optional[bool]

    include_object_storage_size: Optional[bool]

    include_table_storage_size: Optional[bool]

    include_trace_storage_size: Optional[bool]
