# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from .._models import BaseModel

__all__ = ["FeedbackPayloadSchemaResponse", "Path"]


class Path(BaseModel):
    """Discovered path in feedback payload with inferred type."""

    json_path: str
    """Dot path into payload (e.g. 'output.score')."""

    value_type: Optional[Literal["numeric", "boolean", "categorical"]] = None
    """Inferred type of value at path."""


class FeedbackPayloadSchemaResponse(BaseModel):
    """Response with discovered feedback payload paths and types."""

    paths: Optional[List[Path]] = None
    """Discovered leaf paths with inferred value types."""
