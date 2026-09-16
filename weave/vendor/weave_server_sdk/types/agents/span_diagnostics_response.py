# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import List, Optional
from typing_extensions import Literal

from ..._models import BaseModel

__all__ = ["SpanDiagnosticsResponse", "Finding", "FindingField"]


class FindingField(BaseModel):
    attribute_name: str

    name: Literal["input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"]

    value: Optional[int] = None


class Finding(BaseModel):
    excess_tokens: int

    explanation: str

    fields: List[FindingField]

    span_id: str

    trace_id: str

    certainty: Optional[Literal["confirmed"]] = None

    code: Optional[Literal["cache_tokens_exceed_input"]] = None

    impact: Optional[Literal["cost"]] = None

    remediation: Optional[str] = None

    rule_version: Optional[Literal[1]] = None

    title: Optional[str] = None


class SpanDiagnosticsResponse(BaseModel):
    """Results cover one accounting rule on the selected span, not trace health."""

    status: Literal["evaluated", "not_found", "not_evaluated"]

    findings: Optional[List[Finding]] = None

    scope: Optional[Literal["selected_span"]] = None
