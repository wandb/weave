# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel

__all__ = ["DatasetSourceLinkResponse", "Entry"]


class Entry(BaseModel):
    """Result for a single flattened (row_digest, source) link."""

    link_id: str

    created: Optional[bool] = None


class DatasetSourceLinkResponse(BaseModel):
    """Response from linking dataset rows to sources.

    One entry per flattened (row_digest, source) tuple, in input order.
    """

    entries: List[Entry]
