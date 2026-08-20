# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel

__all__ = ["TableQueryResponse", "Row"]


class Row(BaseModel):
    digest: str

    val: object

    original_index: Optional[int] = None


class TableQueryResponse(BaseModel):
    rows: List[Row]
