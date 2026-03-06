from __future__ import annotations

from unittest.mock import Mock

from google.cloud.aiplatform_v1beta1.types import content as gapic_content_types
from google.cloud.aiplatform_v1beta1.types import tool as gapic_tool_types

from weave.integrations.vertexai.vertexai_sdk import vertexai_accumulator


def _make_text_part_mock(text: str) -> Mock:
    """Mock a VertexAI SDK Part whose .text returns the given string."""
    part = Mock(spec=["text", "_raw_part"])
    part.text = text
    part._raw_part = gapic_content_types.Part(text=text)
    return part


def _make_function_call_part_mock(
    name: str, args: dict | None = None
) -> Mock:
    """Mock a VertexAI SDK Part whose .text raises AttributeError.

    Uses spec=['_raw_part'] so that accessing .text raises AttributeError
    naturally (it's not in the spec), just like the real SDK Part does for
    non-text parts.
    """
    raw_part = gapic_content_types.Part(
        function_call=gapic_tool_types.FunctionCall(
            name=name,
            args=args or {},
        )
    )
    part = Mock(spec=["_raw_part"])
    part._raw_part = raw_part
    return part


def _make_response_mock(
    parts: list[Mock],
    role: str = "model",
    prompt_token_count: int = 0,
    candidates_token_count: int = 0,
    total_token_count: int = 0,
) -> Mock:
    """Mock a VertexAI GenerationResponse with one candidate."""
    content = Mock()
    content.parts = parts
    content.role = role

    candidate = Mock()
    candidate.content = content

    usage = Mock()
    usage.prompt_token_count = prompt_token_count
    usage.candidates_token_count = candidates_token_count
    usage.total_token_count = total_token_count

    response = Mock()
    response.candidates = [candidate]
    response.usage_metadata = usage
    return response


# ---- tests ----


def test_function_call_part_does_not_raise():
    """A function_call part must not crash the accumulator (the original bug)."""
    acc = _make_response_mock(
        [_make_text_part_mock("thinking...")],
    )
    value = _make_response_mock(
        [_make_function_call_part_mock("replace_text", {"file": "index.html"})],
    )

    result = vertexai_accumulator(acc, value)

    fc = result.candidates[0].content.parts[0].function_call
    assert fc.name == "replace_text"


def test_mixed_text_and_function_call_parts():
    """Candidate with both a text part and a function_call part."""
    acc = _make_response_mock(
        [_make_text_part_mock("Plan: "), _make_text_part_mock("ignored")],
    )
    value = _make_response_mock(
        [
            _make_text_part_mock("edit the file"),
            _make_function_call_part_mock("edit_file", {"path": "main.py"}),
        ],
    )

    result = vertexai_accumulator(acc, value)

    assert result.candidates[0].content.parts[0].text == "Plan: edit the file"
    assert result.candidates[0].content.parts[1].function_call.name == "edit_file"


def test_value_has_more_parts_than_acc():
    """Value introduces a new function_call part not present in acc."""
    acc = _make_response_mock([_make_text_part_mock("Hello")])
    value = _make_response_mock(
        [
            _make_text_part_mock(" World"),
            _make_function_call_part_mock("do_thing"),
        ],
    )

    result = vertexai_accumulator(acc, value)

    assert result.candidates[0].content.parts[0].text == "Hello World"
    assert result.candidates[0].content.parts[1].function_call.name == "do_thing"


def test_function_call_only_chunks():
    """Both acc and value contain only function_call parts (no text at all)."""
    acc = _make_response_mock(
        [_make_function_call_part_mock("search", {"q": "hello"})],
    )
    value = _make_response_mock(
        [_make_function_call_part_mock("replace", {"old": "a", "new": "b"})],
    )

    result = vertexai_accumulator(acc, value)

    fc = result.candidates[0].content.parts[0].function_call
    assert fc.name == "replace"
