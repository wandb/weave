# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel

__all__ = ["TableUpdateResponse"]


class TableUpdateResponse(BaseModel):
    digest: str

    updated_row_digests: Optional[List[str]] = None
    """The digests of the rows that were updated"""
