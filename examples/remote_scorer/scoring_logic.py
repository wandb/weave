"""Framework-independent scoring logic for the remote scorer sample.

One endpoint accepts every request shape Weave can send:

- ``schema_version: 1`` wraps a call under ``original_call``.
- ``schema_version: 2`` wraps a ``scoring_target`` union whose ``type`` and
  inner ``schema_version`` select the payload. Call monitors and agent-turn
  monitors share this envelope.

Dispatch first on the top-level ``schema_version``, then on the pair
``(scoring_target.type, scoring_target.schema_version)``. A new target type
extends the V2 union and starts at inner schema version 1, so an endpoint
should reject a pair it does not implement instead of guessing.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_SCHEMA_VERSIONS = frozenset({1, 2})
SUPPORTED_SCORING_TARGETS = frozenset({("call", 1), ("agent_turn", 1)})

CONCISE_MESSAGE_LENGTH = 120
TOO_LONG_MESSAGE_LENGTH = 500


class UnsupportedScoringTargetError(ValueError):
    """The request is well formed but names a scoring target we do not score."""


def read_schema_version(request_body: dict[str, Any]) -> int:
    """Return the top-level schema version, or raise if it is not supported."""
    schema_version = request_body.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or schema_version not in SUPPORTED_SCHEMA_VERSIONS
    ):
        raise ValueError("unsupported remote scorer schema_version")
    return schema_version


def extract_scoring_target(
    request_body: dict[str, Any],
) -> tuple[str, int, dict[str, Any]]:
    """Return ``(type, schema_version, payload)`` for either envelope version.

    V1 has no ``scoring_target`` field; its ``original_call`` is the same
    payload V2 carries as the ``("call", 1)`` target.
    """
    schema_version = read_schema_version(request_body)

    if schema_version == 1:
        original_call = request_body.get("original_call")
        if not isinstance(original_call, dict):
            raise TypeError("request missing original_call object")
        return "call", 1, original_call

    scoring_target = request_body.get("scoring_target")
    if not isinstance(scoring_target, dict):
        raise TypeError("request missing scoring_target object")
    target_type = scoring_target.get("type")
    target_version = scoring_target.get("schema_version")
    payload = scoring_target.get("payload")
    if not isinstance(target_type, str):
        raise TypeError("scoring_target.type must be a string")
    if isinstance(target_version, bool) or not isinstance(target_version, int):
        raise TypeError("scoring_target.schema_version must be an integer")
    if not isinstance(payload, dict):
        raise TypeError("scoring_target.payload must be an object")
    return target_type, target_version, payload


def score_remote_request(request_body: dict[str, Any]) -> list[dict[str, Any]]:
    """Score one Weave remote scorer request of any supported version."""
    target_type, target_version, payload = extract_scoring_target(request_body)

    if (target_type, target_version) not in SUPPORTED_SCORING_TARGETS:
        raise UnsupportedScoringTargetError(
            f"unsupported scoring target {target_type!r} version {target_version}"
        )
    if target_type == "call":
        return score_call(payload)
    return score_agent_turn(payload)


def score_call(original_call: dict[str, Any]) -> list[dict[str, Any]]:
    """Score a traced call by the length of its ``inputs.message``."""
    inputs = original_call.get("inputs", {})
    message = inputs.get("message", "") if isinstance(inputs, dict) else ""
    return score_text_length(message if isinstance(message, str) else "")


def score_agent_turn(agent_turn: dict[str, Any]) -> list[dict[str, Any]]:
    """Score an agent turn by the length of its last assistant output message.

    ``messages.output`` lists the normalized messages the agent produced during
    the turn. ``content`` is plain text, or a JSON-encoded array of parts when
    the message carried structured content. This sample treats both as text.
    """
    messages = agent_turn.get("messages", {})
    output = messages.get("output", []) if isinstance(messages, dict) else []
    last_content = ""
    if isinstance(output, list) and output:
        last_message = output[-1]
        if isinstance(last_message, dict):
            content = last_message.get("content", "")
            last_content = content if isinstance(content, str) else ""
    return score_text_length(last_content)


def score_text_length(text: str) -> list[dict[str, Any]]:
    """Return one numeric rating and one tag describing how concise ``text`` is.

    Replace this with your real policy, model, or business logic. It is
    deliberately independent of FastAPI so it can be copied into another service
    framework or language.
    """
    message_length = len(text)

    if message_length <= CONCISE_MESSAGE_LENGTH:
        conciseness_rating = 1.0
        length_tag = "concise"
    elif message_length >= TOO_LONG_MESSAGE_LENGTH:
        conciseness_rating = 0.0
        length_tag = "too-long"
    else:
        conciseness_rating = 1 - (
            (message_length - CONCISE_MESSAGE_LENGTH)
            / (TOO_LONG_MESSAGE_LENGTH - CONCISE_MESSAGE_LENGTH)
        )
        length_tag = "verbose"

    return [
        {
            "value": round(conciseness_rating, 2),
            "reason": (
                f"Message is {message_length} characters; concise messages score best."
            ),
            "confidence": 1.0,
        },
        {
            "value": length_tag,
            "reason": f"Message length category is {length_tag}.",
            "confidence": 0.9,
        },
    ]
