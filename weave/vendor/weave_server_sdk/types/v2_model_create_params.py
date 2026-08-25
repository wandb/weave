# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2ModelCreateParams"]


class V2ModelCreateParams(TypedDict, total=False):
    entity: Required[str]

    name: Required[str]
    """The name of this model. Models with the same name will be versioned together."""

    source_code: Required[str]
    """Complete source code for the Model class including imports"""

    attributes: Optional[Dict[str, object]]
    """Additional attributes to be stored with the model"""

    description: Optional[str]
    """A description of this model"""
