# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from datetime import datetime

from .._models import BaseModel

__all__ = ["ObjectReadResponse", "Obj"]


class Obj(BaseModel):
    base_object_class: Optional[str] = None

    created_at: datetime

    digest: str

    is_latest: int

    kind: str

    object_id: str

    project_id: str

    val: object

    version_index: int

    aliases: Optional[List[str]] = None

    deleted_at: Optional[datetime] = None

    leaf_object_class: Optional[str] = None

    size_bytes: Optional[int] = None

    tags: Optional[List[str]] = None

    wb_user_id: Optional[str] = None
    """Do not set directly. Server will automatically populate this field."""


class ObjectReadResponse(BaseModel):
    obj: Obj
