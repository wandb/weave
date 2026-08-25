# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel

__all__ = ["TableQueryStatsBatchResponse", "Table"]


class Table(BaseModel):
    count: int

    digest: str

    storage_size_bytes: Optional[int] = None


class TableQueryStatsBatchResponse(BaseModel):
    tables: List[Table]
