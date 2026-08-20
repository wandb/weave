# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2ScorerCreateParams"]


class V2ScorerCreateParams(TypedDict, total=False):
    entity: Required[str]

    name: Required[str]
    """The name of this scorer. Scorers with the same name will be versioned together."""

    op_source_code: Required[str]
    """Complete source code for the Scorer.score op including imports"""

    description: Optional[str]
    """A description of this scorer"""
