"""Tests for the ContentAdaptable extension API."""

from __future__ import annotations

import base64
import json

import pytest
from pydantic import ValidationError

from weave.type_wrappers.Content.content import (
    Content,
    ContentAdaptable,
    _content_adapters,
    register_content_adapter,
)


@pytest.fixture(autouse=True)
def _clean_adapter_registry():
    """Snapshot and restore the global adapter list around each test."""
    before = list(_content_adapters)
    yield
    _content_adapters[:] = before


# ── Dummy adapter for unit tests ────────────────────────────────────────


class DummyAdaptable(ContentAdaptable):
    kind: str
    payload: str

    def to_content(self) -> Content:
        return Content.from_text(self.payload)


# ── ContentAdaptable base ───────────────────────────────────────────────


class TestContentAdaptable:
    def test_subclass_validates(self):
        obj = DummyAdaptable.model_validate({"kind": "dummy", "payload": "hello"})
        assert obj.kind == "dummy"
        assert obj.payload == "hello"

    def test_subclass_rejects_missing_fields(self):
        with pytest.raises(ValidationError):
            DummyAdaptable.model_validate({"kind": "dummy"})

    def test_extra_fields_allowed(self):
        obj = DummyAdaptable.model_validate(
            {"kind": "dummy", "payload": "hi", "extra": 123}
        )
        assert obj.payload == "hi"

    def test_to_content(self):
        obj = DummyAdaptable(kind="dummy", payload="test")
        content = obj.to_content()
        assert content.as_string() == "test"


# ── is_content_like ─────────────────────────────────────────────────────


class TestIsContentLike:
    def test_registered_adapter_matches_dict(self):
        register_content_adapter(DummyAdaptable)
        assert Content.is_content_like({"kind": "dummy", "payload": "hello"})

    def test_unregistered_adapter_not_matched(self):
        assert not Content.is_content_like({"kind": "dummy", "payload": "hello"})

    def test_validated_model_instance_matches(self):
        obj = DummyAdaptable(kind="dummy", payload="hello")
        assert Content.is_content_like(obj)

    def test_builtin_types(self):
        assert Content.is_content_like("hello")
        assert Content.is_content_like(b"bytes")

    def test_rejects_unknown_types(self):
        assert not Content.is_content_like(42)
        assert not Content.is_content_like(None)
        assert not Content.is_content_like([1, 2, 3])

    def test_dict_not_matching_any_adapter(self):
        register_content_adapter(DummyAdaptable)
        assert not Content.is_content_like({"unrelated": "dict"})


# ── _from_guess with adapters ───────────────────────────────────────────


class TestFromGuessWithAdapter:
    def test_from_guess_with_validated_model(self):
        register_content_adapter(DummyAdaptable)
        obj = DummyAdaptable(kind="dummy", payload="typed input")
        content = Content._from_guess(obj)
        assert content.as_string() == "typed input"

    def test_from_guess_validates_raw_dict(self):
        register_content_adapter(DummyAdaptable)
        content = Content._from_guess({"kind": "dummy", "payload": "raw dict"})
        assert content.as_string() == "raw dict"

    def test_from_guess_falls_back_to_builtins(self):
        register_content_adapter(DummyAdaptable)
        content = Content._from_guess("plain text input")
        assert content.as_string() == "plain text input"

    def test_from_guess_adapter_priority(self):
        """First matching adapter wins."""

        class HighPriority(ContentAdaptable):
            kind: str

            def to_content(self) -> Content:
                return Content.from_text("high priority")

        register_content_adapter(HighPriority)
        register_content_adapter(DummyAdaptable)

        content = Content._from_guess({"kind": "dummy", "payload": "low priority"})
        assert content.as_string() == "high priority"


# ── OTel GenAI blob adapter ─────────────────────────────────────────────


class TestGenAIBlobAdapter:
    @pytest.fixture(autouse=True)
    def _register_genai_adapter(self):
        import weave.type_wrappers.Content.adapters  # noqa: F401

    def test_blob_dict_is_content_like(self):
        blob = {"type": "blob", "data": "AAAA", "mime_type": "image/png"}
        assert Content.is_content_like(blob)

    def test_blob_dict_missing_fields_not_content_like(self):
        assert not Content.is_content_like({"type": "blob"})
        assert not Content.is_content_like({"type": "blob", "data": "AAAA"})
        assert not Content.is_content_like({"type": "blob", "mime_type": "image/png"})

    def test_non_blob_dict_not_content_like(self):
        assert not Content.is_content_like({"type": "text", "content": "hi"})

    def test_from_guess_converts_blob(self):
        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        b64 = base64.b64encode(raw).decode("ascii")
        blob = {"type": "blob", "data": b64, "mime_type": "image/png"}

        content = Content._from_guess(blob)
        assert content.data == raw
        assert content.mimetype == "image/png"

    def test_from_guess_with_validated_genai_blob(self):
        from weave.type_wrappers.Content.adapters import GenAIBlob

        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        b64 = base64.b64encode(raw).decode("ascii")
        blob = GenAIBlob(type="blob", data=b64, mime_type="image/png")

        content = Content._from_guess(blob)
        assert content.data == raw
        assert content.mimetype == "image/png"


# ── Google Part adapters ────────────────────────────────────────────────


class TestGooglePartAdapters:
    """Test every Google Part adapter can convert its field to Content."""

    @pytest.fixture(autouse=True)
    def _register_adapters(self):
        import weave.type_wrappers.Content.adapters  # noqa: F401

    # -- inline_data (active by default) ----------------------------------

    def test_inline_data_from_base64_string(self):
        from weave.type_wrappers.Content.adapters import GooglePartInlineData

        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        b64 = base64.b64encode(raw).decode("ascii")
        adapter = GooglePartInlineData.model_validate(
            {"inline_data": {"data": b64, "mime_type": "image/png"}}
        )
        content = adapter.to_content()
        assert content.data == raw
        assert content.mimetype == "image/png"
        assert content.metadata["adapter_type"] == "google:part:inline_data"

    def test_inline_data_from_raw_bytes(self):
        from weave.type_wrappers.Content.adapters import GooglePartInlineData

        raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        adapter = GooglePartInlineData.model_validate(
            {"inline_data": {"data": raw, "mime_type": "image/png"}}
        )
        content = adapter.to_content()
        assert content.data == raw

    def test_inline_data_via_from_guess(self):
        part = {"inline_data": {"data": "AAAA", "mime_type": "image/png"}}
        assert Content.is_content_like(part)
        content = Content._from_guess(part)
        assert content.metadata["adapter_type"] == "google:part:inline_data"

    # -- text -------------------------------------------------------------

    def test_text_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartText

        adapter = GooglePartText(text="Hello world")
        content = adapter.to_content()
        assert content.as_string() == "Hello world"
        assert content.metadata["adapter_type"] == "google:part:text"

    # -- file_data --------------------------------------------------------

    def test_file_data_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartFileData

        adapter = GooglePartFileData.model_validate(
            {
                "file_data": {
                    "file_uri": "gs://bucket/image.png",
                    "mime_type": "image/png",
                }
            }
        )
        content = adapter.to_content()
        payload = json.loads(content.as_string())
        assert payload["file_uri"] == "gs://bucket/image.png"
        assert content.metadata["adapter_type"] == "google:part:file_data"

    # -- executable_code --------------------------------------------------

    def test_executable_code_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartExecutableCode

        adapter = GooglePartExecutableCode.model_validate(
            {"executable_code": {"code": "print('hi')", "language": "PYTHON"}}
        )
        content = adapter.to_content()
        assert content.as_string() == "print('hi')"
        assert content.metadata["language"] == "PYTHON"

    # -- code_execution_result --------------------------------------------

    def test_code_execution_result_adapter(self):
        from weave.type_wrappers.Content.adapters import (
            GooglePartCodeExecutionResult,
        )

        adapter = GooglePartCodeExecutionResult.model_validate(
            {"code_execution_result": {"outcome": "SUCCESS", "output": "hi\n"}}
        )
        content = adapter.to_content()
        assert content.as_string() == "hi\n"
        assert content.metadata["outcome"] == "SUCCESS"

    # -- function_call ----------------------------------------------------

    def test_function_call_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartFunctionCall

        adapter = GooglePartFunctionCall.model_validate(
            {"function_call": {"name": "get_weather", "args": {"city": "NYC"}}}
        )
        content = adapter.to_content()
        payload = json.loads(content.as_string())
        assert payload["name"] == "get_weather"
        assert payload["args"]["city"] == "NYC"

    # -- function_response ------------------------------------------------

    def test_function_response_adapter(self):
        from weave.type_wrappers.Content.adapters import (
            GooglePartFunctionResponse,
        )

        adapter = GooglePartFunctionResponse.model_validate(
            {
                "function_response": {
                    "name": "get_weather",
                    "response": {"temp": 72},
                }
            }
        )
        content = adapter.to_content()
        payload = json.loads(content.as_string())
        assert payload["response"]["temp"] == 72

    # -- thought ----------------------------------------------------------

    def test_thought_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartThought

        adapter = GooglePartThought(thought=True)
        content = adapter.to_content()
        assert content.as_string() == "True"

    # -- thought_signature ------------------------------------------------

    def test_thought_signature_adapter(self):
        from weave.type_wrappers.Content.adapters import (
            GooglePartThoughtSignature,
        )

        sig = b"\xde\xad\xbe\xef"
        adapter = GooglePartThoughtSignature(thought_signature=sig)
        content = adapter.to_content()
        assert content.data == sig

    # -- tool_call / tool_response ----------------------------------------

    def test_tool_call_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartToolCall

        adapter = GooglePartToolCall(tool_call={"id": "tc_1", "name": "search"})
        content = adapter.to_content()
        assert json.loads(content.as_string())["id"] == "tc_1"

    def test_tool_response_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartToolResponse

        adapter = GooglePartToolResponse(tool_response={"id": "tc_1", "output": "done"})
        content = adapter.to_content()
        assert json.loads(content.as_string())["output"] == "done"

    # -- video_metadata ---------------------------------------------------

    def test_video_metadata_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartVideoMetadata

        adapter = GooglePartVideoMetadata(
            video_metadata={"start_offset": "0s", "end_offset": "5s"}
        )
        content = adapter.to_content()
        assert json.loads(content.as_string())["start_offset"] == "0s"

    # -- media_resolution / part_metadata ---------------------------------

    def test_media_resolution_adapter(self):
        from weave.type_wrappers.Content.adapters import (
            GooglePartMediaResolution,
        )

        adapter = GooglePartMediaResolution(media_resolution={"level": "MEDIUM"})
        content = adapter.to_content()
        assert json.loads(content.as_string())["level"] == "MEDIUM"

    def test_part_metadata_adapter(self):
        from weave.type_wrappers.Content.adapters import GooglePartMetadata

        adapter = GooglePartMetadata(part_metadata={"source": "upload"})
        content = adapter.to_content()
        assert json.loads(content.as_string())["source"] == "upload"


class TestActiveConversionList:
    """Only adapters in ACTIVE_GOOGLE_PART_CONVERSIONS are registered."""

    @pytest.fixture(autouse=True)
    def _register_adapters(self):
        import weave.type_wrappers.Content.adapters  # noqa: F401

    def test_active_inline_data_matches(self):
        part = {"inline_data": {"data": "AAAA", "mime_type": "image/png"}}
        assert Content.is_content_like(part)

    def test_active_file_data_matches(self):
        part = {
            "file_data": {
                "file_uri": "gs://bucket/img.png",
                "mime_type": "image/png",
            }
        }
        assert Content.is_content_like(part)

    def test_inactive_adapter_does_not_match(self):
        """Text adapter exists but is not in the active set."""
        part = {"text": "Hello"}
        assert not Content.is_content_like(part)

    def test_inactive_adapter_still_works_directly(self):
        from weave.type_wrappers.Content.adapters import GooglePartText

        content = GooglePartText(text="direct call").to_content()
        assert content.as_string() == "direct call"

    def test_can_activate_adapter_at_runtime(self):
        from weave.type_wrappers.Content.adapters import GooglePartText

        register_content_adapter(GooglePartText)
        part = {"text": "now active"}
        assert Content.is_content_like(part)
        content = Content._from_guess(part)
        assert content.as_string() == "now active"
