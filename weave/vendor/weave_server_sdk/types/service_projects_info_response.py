# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List
from typing_extensions import TypeAlias

from .._models import BaseModel

__all__ = ["ServiceProjectsInfoResponse", "ServiceProjectsInfoResponseItem"]


class ServiceProjectsInfoResponseItem(BaseModel):
    external_project_id: str
    """External project ID in 'entity/project' format."""

    internal_project_id: str
    """Internal project ID."""


ServiceProjectsInfoResponse: TypeAlias = List[ServiceProjectsInfoResponseItem]
