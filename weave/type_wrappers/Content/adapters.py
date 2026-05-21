"""Built-in ContentAdaptable implementations.

Adapters for:
* OTel GenAI blob parts  (flat span-attribute format)
* Google GenAI SDK Part types  (nested ``{field: {...}}`` format)
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel

from weave.type_wrappers.Content.content import (
    Content,
    ContentAdaptable,
    register_content_adapter,
)

# ---------------------------------------------------------------------------
# OTel GenAI blob adapter  (flat span-attribute format)
# ---------------------------------------------------------------------------


class GenAIBlob(ContentAdaptable):
    """Google GenAI OTel blob part.

    Spans encode binary data as::

        {"type": "blob", "data": "<base64>", "mime_type": "image/png"}
    """

    type: Literal["blob"]
    data: str
    mime_type: str

    def to_content(self) -> Content:
        return Content.from_base64(self.data, mimetype=self.mime_type)


# ---------------------------------------------------------------------------
# Google GenAI SDK Part sub-models
# ---------------------------------------------------------------------------


class _BlobModel(BaseModel):
    data: str | bytes
    mime_type: str


class _FileDataModel(BaseModel):
    file_uri: str
    mime_type: str
    display_name: str | None = None


class _ExecutableCodeModel(BaseModel):
    code: str
    language: str | None = None


class _CodeExecutionResultModel(BaseModel):
    outcome: str | None = None
    output: str


class _FunctionCallModel(BaseModel):
    name: str
    args: dict[str, Any] | None = None


class _FunctionResponseModel(BaseModel):
    name: str
    response: dict[str, Any]


# ---------------------------------------------------------------------------
# Google Part adapters — one per Part field type
# ---------------------------------------------------------------------------


class GooglePartInlineData(ContentAdaptable):
    inline_data: _BlobModel

    def to_content(self) -> Content:
        d = self.inline_data
        if isinstance(d.data, bytes):
            return Content.from_bytes(
                d.data,
                mimetype=d.mime_type,
                metadata={"adapter_type": "google:part:inline_data"},
            )
        return Content.from_base64(
            d.data,
            mimetype=d.mime_type,
            metadata={"adapter_type": "google:part:inline_data"},
        )


class GooglePartText(ContentAdaptable):
    text: str

    def to_content(self) -> Content:
        return Content.from_text(
            self.text,
            metadata={"adapter_type": "google:part:text"},
        )


class GooglePartFileData(ContentAdaptable):
    file_data: _FileDataModel

    def to_content(self) -> Content:
        return Content.from_text(
            json.dumps(self.file_data.model_dump()),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:file_data"},
        )


class GooglePartExecutableCode(ContentAdaptable):
    executable_code: _ExecutableCodeModel

    def to_content(self) -> Content:
        meta: dict[str, Any] = {"adapter_type": "google:part:executable_code"}
        if self.executable_code.language:
            meta["language"] = self.executable_code.language
        return Content.from_text(self.executable_code.code, metadata=meta)


class GooglePartCodeExecutionResult(ContentAdaptable):
    code_execution_result: _CodeExecutionResultModel

    def to_content(self) -> Content:
        meta: dict[str, Any] = {
            "adapter_type": "google:part:code_execution_result",
        }
        if self.code_execution_result.outcome:
            meta["outcome"] = self.code_execution_result.outcome
        return Content.from_text(self.code_execution_result.output, metadata=meta)


class GooglePartFunctionCall(ContentAdaptable):
    function_call: _FunctionCallModel

    def to_content(self) -> Content:
        payload = {
            "name": self.function_call.name,
            "args": self.function_call.args,
        }
        return Content.from_text(
            json.dumps(payload),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:function_call"},
        )


class GooglePartFunctionResponse(ContentAdaptable):
    function_response: _FunctionResponseModel

    def to_content(self) -> Content:
        payload = {
            "name": self.function_response.name,
            "response": self.function_response.response,
        }
        return Content.from_text(
            json.dumps(payload),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:function_response"},
        )


class GooglePartThought(ContentAdaptable):
    thought: bool

    def to_content(self) -> Content:
        return Content.from_text(
            str(self.thought),
            metadata={"adapter_type": "google:part:thought"},
        )


class GooglePartThoughtSignature(ContentAdaptable):
    thought_signature: bytes

    def to_content(self) -> Content:
        return Content.from_bytes(
            self.thought_signature,
            metadata={"adapter_type": "google:part:thought_signature"},
        )


class GooglePartVideoMetadata(ContentAdaptable):
    video_metadata: dict[str, Any]

    def to_content(self) -> Content:
        return Content.from_text(
            json.dumps(self.video_metadata),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:video_metadata"},
        )


class GooglePartToolCall(ContentAdaptable):
    tool_call: dict[str, Any]

    def to_content(self) -> Content:
        return Content.from_text(
            json.dumps(self.tool_call),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:tool_call"},
        )


class GooglePartToolResponse(ContentAdaptable):
    tool_response: dict[str, Any]

    def to_content(self) -> Content:
        return Content.from_text(
            json.dumps(self.tool_response),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:tool_response"},
        )


class GooglePartMediaResolution(ContentAdaptable):
    media_resolution: dict[str, Any]

    def to_content(self) -> Content:
        return Content.from_text(
            json.dumps(self.media_resolution),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:media_resolution"},
        )


class GooglePartMetadata(ContentAdaptable):
    part_metadata: dict[str, Any]

    def to_content(self) -> Content:
        return Content.from_text(
            json.dumps(self.part_metadata),
            mimetype="application/json",
            metadata={"adapter_type": "google:part:part_metadata"},
        )


# ---------------------------------------------------------------------------
# Registry of all Google Part adapters (keyed by Part field name)
# ---------------------------------------------------------------------------

GOOGLE_PART_ADAPTERS: dict[str, type[ContentAdaptable]] = {
    "inline_data": GooglePartInlineData,
    "text": GooglePartText,
    "file_data": GooglePartFileData,
    "executable_code": GooglePartExecutableCode,
    "code_execution_result": GooglePartCodeExecutionResult,
    "function_call": GooglePartFunctionCall,
    "function_response": GooglePartFunctionResponse,
    "thought": GooglePartThought,
    "thought_signature": GooglePartThoughtSignature,
    "video_metadata": GooglePartVideoMetadata,
    "tool_call": GooglePartToolCall,
    "tool_response": GooglePartToolResponse,
    "media_resolution": GooglePartMediaResolution,
    "part_metadata": GooglePartMetadata,
}

# Part types whose data should be stored as weave Content objects.
# Add or remove entries to control which Part types trigger conversion
# without touching the adapter implementations above.
ACTIVE_GOOGLE_PART_CONVERSIONS: set[str] = {
    "inline_data",
    "file_data",
}

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

# OTel blob adapter (always active)
register_content_adapter(GenAIBlob)

# Google Part adapters (only active subset)
for _part_name in ACTIVE_GOOGLE_PART_CONVERSIONS:
    register_content_adapter(GOOGLE_PART_ADAPTERS[_part_name])
