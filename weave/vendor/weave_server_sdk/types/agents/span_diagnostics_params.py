# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing_extensions import Required, TypedDict

__all__ = ["SpanDiagnosticsParams"]


class SpanDiagnosticsParams(TypedDict, total=False):
    project_id: Required[str]

    span_id: Required[str]

    trace_id: Required[str]
