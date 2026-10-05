# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from datetime import datetime
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["DatasetSourceSourceDatasetsQueryResponse", "Membership"]


class Membership(BaseModel):
    """Membership of a single (source, dataset) pair in the reverse query."""

    dataset_object_id: str

    first_seen_at: datetime

    row_digests: List[str]

    row_digests_total_count: int

    row_digests_truncated: bool

    source_id: str

    source_kind: Literal["call", "span", "conversation"]

    source_trace_id: str


class DatasetSourceSourceDatasetsQueryResponse(BaseModel):
    """Response from the reverse sources -> datasets query."""

    memberships: List[Membership]
