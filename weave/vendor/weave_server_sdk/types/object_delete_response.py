# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional

from .._models import BaseModel

__all__ = ["ObjectDeleteResponse", "DeletedVersion"]


class DeletedVersion(BaseModel):
    digest: str

    base_object_class: Optional[str] = None

    leaf_object_class: Optional[str] = None


class ObjectDeleteResponse(BaseModel):
    num_deleted: int

    deleted_versions: Optional[List[DeletedVersion]] = None
    """
    Metadata for each deleted object version, with digest aliases resolved to
    content digests. None when the backing server does not report it.
    """
