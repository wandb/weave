# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["SpanCustomAttrsSchemaResponse", "Attribute"]


class Attribute(BaseModel):
    """One custom attribute key/type observed in the matching spans."""

    key: str

    source: Literal["custom_attrs_string", "custom_attrs_int", "custom_attrs_float", "custom_attrs_bool"]

    span_count: int

    value_type: Literal["string", "int", "float", "bool"]


class SpanCustomAttrsSchemaResponse(BaseModel):
    """Typed custom attribute keys available for spans query/group/stats APIs."""

    attributes: Optional[List[Attribute]] = None

    has_more: Optional[bool] = None

    limit: Optional[int] = None

    offset: Optional[int] = None
