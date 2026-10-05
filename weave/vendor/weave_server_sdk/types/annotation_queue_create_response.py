# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel

__all__ = ["AnnotationQueueCreateResponse"]


class AnnotationQueueCreateResponse(BaseModel):
    """Response from creating an annotation queue."""

    id: str
