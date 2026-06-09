"""Framework-independent scoring logic for the remote scorer sample."""

from __future__ import annotations

from typing import Any

REMOTE_SCORER_SCHEMA_VERSION = 1


def score_remote_call(request_body: dict[str, Any]) -> dict[str, Any]:
    """Score one Weave remote scorer request.

    Replace this function with your real policy, model, or business logic. It is
    deliberately independent of FastAPI so it can be copied into another service
    framework or language.
    """
    if request_body.get("schema_version") != REMOTE_SCORER_SCHEMA_VERSION:
        raise ValueError("unsupported remote scorer schema_version")

    original_call = request_body.get("original_call")
    if not isinstance(original_call, dict):
        raise ValueError("request missing original_call object")

    inputs = original_call.get("inputs", {})
    message = inputs.get("message", "") if isinstance(inputs, dict) else ""
    if not isinstance(message, str):
        message = ""

    return {
        "message_length": len(message),
    }
