# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["V2EvaluationCreateParams"]


class V2EvaluationCreateParams(TypedDict, total=False):
    entity: Required[str]

    dataset: Required[str]
    """Reference to the dataset (weave:// URI)"""

    name: Required[str]
    """The name of this evaluation.

    Evaluations with the same name will be versioned together.
    """

    description: Optional[str]
    """A description of this evaluation"""

    eval_attributes: Optional[Dict[str, object]]
    """Optional attributes for the evaluation"""

    evaluation_name: Optional[str]
    """Name for the evaluation run"""

    scorers: Optional[SequenceNotStr[str]]
    """List of scorer references (weave:// URIs)"""

    trials: int
    """Number of trials to run"""
