"""Validate call start and end requests when the call is created.

The request models used to validate these when they were built, so a call with a
bad field failed in the client instead of joining a batch the server rejects as a
whole.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Any

from pydantic import TypeAdapter

from weave.vendor.weave_server_sdk.types import CallEndParams, CallStartParams


@cache
def _call_start_adapter() -> TypeAdapter[CallStartParams]:
    return TypeAdapter(CallStartParams)


@cache
def _call_end_adapter() -> TypeAdapter[CallEndParams]:
    return TypeAdapter(CallEndParams)


def validate_call_start(req: Mapping[str, Any]) -> None:
    """Raise `pydantic.ValidationError` if the start request has a bad field."""
    _call_start_adapter().validate_python(req)


def validate_call_end(req: Mapping[str, Any]) -> None:
    """Raise `pydantic.ValidationError` if the end request has a bad field."""
    _call_end_adapter().validate_python(req)
