# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["ServiceProjectsInfoParams"]


class ServiceProjectsInfoParams(TypedDict, total=False):
    project_ids: Required[SequenceNotStr[str]]
    """External project IDs in 'entity/project' format."""
