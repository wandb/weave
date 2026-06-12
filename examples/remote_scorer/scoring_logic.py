"""Framework-independent scoring logic for the remote scorer sample."""

from __future__ import annotations

from typing import Any

REMOTE_SCORER_SCHEMA_VERSION = 1
CONCISE_MESSAGE_LENGTH = 120
TOO_LONG_MESSAGE_LENGTH = 500


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
        raise TypeError("request missing original_call object")

    inputs = original_call.get("inputs", {})
    message = inputs.get("message", "") if isinstance(inputs, dict) else ""
    if not isinstance(message, str):
        message = ""
    message_length = len(message)
    if message_length <= CONCISE_MESSAGE_LENGTH:
        rating = 1.0
    elif message_length >= TOO_LONG_MESSAGE_LENGTH:
        rating = 0.0
    else:
        rating = 1 - (
            (message_length - CONCISE_MESSAGE_LENGTH)
            / (TOO_LONG_MESSAGE_LENGTH - CONCISE_MESSAGE_LENGTH)
        )

    return {
        "value": round(rating, 2),
        "reason": (
            f"Message is {message_length} characters; concise messages score best."
        ),
        "confidence": 1.0,
    }
