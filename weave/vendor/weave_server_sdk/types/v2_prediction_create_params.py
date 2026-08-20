# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional
from typing_extensions import Required, TypedDict

__all__ = ["V2PredictionCreateParams", "GenaiSpanRef"]


class V2PredictionCreateParams(TypedDict, total=False):
    entity: Required[str]

    inputs: Required[Dict[str, object]]
    """The inputs to the prediction"""

    model: Required[str]
    """The model reference (weave:// URI)"""

    output: Required[object]
    """The output of the prediction"""

    evaluation_run_id: Optional[str]
    """Optional evaluation run ID to link this prediction as a child call"""

    genai_span_ref: Optional[Iterable[GenaiSpanRef]]
    """Optional GenAI span reference(s) produced by this prediction."""


class GenaiSpanRef(TypedDict, total=False):
    span_id: Required[str]

    trace_id: Required[str]
