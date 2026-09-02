# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional
from typing_extensions import Required, TypedDict

__all__ = ["EvaluationEvaluateModelParams"]


class EvaluationEvaluateModelParams(TypedDict, total=False):
    evaluation_ref: Required[str]

    model_ref: Required[str]

    project_id: Required[str]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
