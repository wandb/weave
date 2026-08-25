# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["ObjectReadParams"]


class ObjectReadParams(TypedDict, total=False):
    digest: Required[str]

    object_id: Required[str]

    project_id: Required[str]

    include_tags_and_aliases: Optional[bool]
    """If true, tags and aliases are fetched and included in the response."""

    metadata_only: Optional[bool]
    """
    If true, the `val` column is not read from the database and is empty.All other
    fields are returned.
    """
