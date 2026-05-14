"""Google → GenAI parts-model serialiser.

Translates ``google.genai.types.Content`` into the GenAI parts-model
JSON shape (`{"role": ..., "parts": [{"type": "text", "content": ...},
{"type": "tool_call", "id": ..., "name": ..., "arguments": ...}, ...]}`)
that the Weave server reads on ingest.

ADK's own ``_to_part`` covers the same shapes when experimental semconv
is opted in (``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental``);
we duplicate the minimal logic so the integration works under the
default semconv too.

# TODO: consolidate with ``weave/session/session_otel.py`` once we land
# a shared ``weave.genai.parts`` module — both this file and the session
# SDK emit the same wire format from different input types, and a third
# integration (anthropic/openai-otel) will arrive soon.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.adk.models.llm_request import LlmRequest
    from google.adk.models.llm_response import LlmResponse


def json_dumps(value: Any) -> str:
    """JSON-encode a value, falling back to ``str(value)`` on failures.

    ADK hands us ``google.genai`` objects whose nested fields are
    pydantic models; ``default=str`` covers anything ``json.dumps``
    doesn't natively understand.
    """
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def content_to_parts(content: Any) -> list[dict[str, Any]]:
    """Flatten a ``google.genai.types.Content`` into the GenAI parts model."""
    parts: list[dict[str, Any]] = []
    for idx, part in enumerate(content.parts or []):
        if part.text is not None:
            parts.append({"type": "text", "content": part.text})
            continue
        fc = part.function_call
        if fc is not None:
            parts.append(
                {
                    "type": "tool_call",
                    "id": fc.id or f"{fc.name or ''}_{idx}",
                    "name": fc.name or "",
                    "arguments": fc.args,
                }
            )
            continue
        fr = part.function_response
        if fr is not None:
            parts.append(
                {
                    "type": "tool_call_response",
                    "id": fr.id or f"{fr.name or ''}_{idx}",
                    "response": fr.response,
                }
            )
            continue
        if part.inline_data is not None:
            # Bytes payloads aren't span-attribute-safe; Weave already
            # stores blobs out of band.
            parts.append(
                {"type": "blob", "mime_type": part.inline_data.mime_type or ""}
            )
            continue
        if part.file_data is not None:
            parts.append(
                {
                    "type": "file",
                    "mime_type": part.file_data.mime_type or "",
                    "uri": part.file_data.file_uri or "",
                }
            )
    return parts


def adk_role_to_weave(role: str | None) -> str:
    """Map ADK's ``"user"``/``"model"`` role labels to the GenAI parts model."""
    if role == "user":
        return "user"
    if role == "model":
        return "assistant"
    return role or ""


def llm_request_input_messages(llm_request: LlmRequest) -> list[dict[str, Any]]:
    """Serialise ``LlmRequest.contents`` to GenAI input-messages JSON shape."""
    return [
        {
            "role": adk_role_to_weave(content.role),
            "parts": content_to_parts(content),
        }
        for content in (llm_request.contents or [])
    ]


def llm_response_output_message(llm_response: LlmResponse) -> dict[str, Any] | None:
    """Serialise an ``LlmResponse`` to the single output-message JSON object.

    Returns ``None`` when the response has no content (e.g. error responses).
    """
    if llm_response.content is None:
        return None
    finish_str = ""
    finish_reason = llm_response.finish_reason
    if finish_reason is not None:
        # ``FinishReason`` is an Enum; ``.value`` is the wire form, fall
        # back to ``.name`` for older enum styles.
        finish_str = str(finish_reason.value or finish_reason.name).lower()
    return {
        "role": adk_role_to_weave(llm_response.content.role) or "assistant",
        "parts": content_to_parts(llm_response.content),
        "finish_reason": finish_str,
    }
