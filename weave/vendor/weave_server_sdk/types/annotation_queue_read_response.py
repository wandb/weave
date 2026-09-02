# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from .._models import BaseModel
from .annotation_queue_schema import AnnotationQueueSchema

__all__ = ["AnnotationQueueReadResponse"]


class AnnotationQueueReadResponse(BaseModel):
    """Response from reading an annotation queue."""

    queue: AnnotationQueueSchema
    """Schema for annotation queue responses."""
