# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["ProjectStatsResponse"]


class ProjectStatsResponse(BaseModel):
    files_storage_size_bytes: int

    objects_storage_size_bytes: int

    tables_storage_size_bytes: int

    trace_storage_size_bytes: int
