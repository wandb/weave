# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.
from __future__ import annotations

from typing import Literal

from weave.chat.types._models import BaseModel

__all__ = ["Model"]


class Model(BaseModel):
    id: str
    """The model identifier, which can be referenced in the API endpoints."""

    # W&B NOTE: We have an inconsistency with OpenAI.
    # It should be a required int, but Inference no longer returns it.
    created: int | None = None
    """The Unix timestamp (in seconds) when the model was created."""

    object: Literal["model"]
    """The object type, which is always "model"."""

    owned_by: str
    """The organization that owns the model."""
