"""Unit tests for Google GenAI Gemini utility functions."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from weave.integrations.google_genai.gemini_utils import (
    google_genai_gemini_accumulator,
    google_genai_gemini_on_finish,
    google_genai_gemini_postprocess_inputs,
)


def make_mock_part(text: str | None = None, thought: bool | None = None) -> MagicMock:
    """Create a mock Part object."""
    part = MagicMock()
    part.text = text
    if thought is not None:
        part.thought = thought
    else:
        # Simulate no thought attribute for non-thinking responses
        del part.thought
    return part


def make_mock_content(parts: list[MagicMock]) -> MagicMock:
    """Create a mock Content object."""
    content = MagicMock()
    content.parts = parts
    return content


def make_mock_candidate(content: MagicMock) -> MagicMock:
    """Create a mock Candidate object."""
    candidate = MagicMock()
    candidate.content = content
    return candidate


def make_mock_usage_metadata(
    prompt_token_count: int | None = None,
    candidates_token_count: int | None = None,
    total_token_count: int | None = None,
    cached_content_token_count: int | None = None,
    thoughts_token_count: int | None = None,
) -> MagicMock:
    """Create a mock UsageMetadata object."""
    usage = MagicMock()
    usage.prompt_token_count = prompt_token_count
    usage.candidates_token_count = candidates_token_count
    usage.total_token_count = total_token_count
    usage.cached_content_token_count = cached_content_token_count
    if thoughts_token_count is not None:
        usage.thoughts_token_count = thoughts_token_count
    else:
        del usage.thoughts_token_count
    return usage


def make_mock_response(
    candidates: list[MagicMock] | None = None,
    usage_metadata: MagicMock | None = None,
) -> MagicMock:
    """Create a mock GenerateContentResponse object."""
    response = MagicMock()
    response.candidates = candidates or []
    response.usage_metadata = usage_metadata or make_mock_usage_metadata()
    return response


class TestGoogleGenaiGeminiAccumulator:
    """Tests for google_genai_gemini_accumulator function."""

    def test_first_chunk_returns_value(self) -> None:
        """Test that the first chunk is returned as-is."""
        value = make_mock_response()
        result = google_genai_gemini_accumulator(None, value)
        assert result is value

    def test_text_accumulation_simple(self) -> None:
        """Test that text is accumulated across chunks."""
        part1 = make_mock_part(text="Hello ")
        part2 = make_mock_part(text="World")

        acc = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([part1]))],
            usage_metadata=make_mock_usage_metadata(),
        )
        value = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([part2]))],
            usage_metadata=make_mock_usage_metadata(),
        )

        result = google_genai_gemini_accumulator(acc, value)
        assert result.candidates[0].content.parts[0].text == "Hello World"

    def test_token_counts_replaced_not_summed(self) -> None:
        """Test that token counts are replaced with latest values, not summed.

        Gemini streaming returns cumulative token counts in the final chunk,
        so we should replace rather than accumulate.
        """
        acc = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([make_mock_part(text="")]))],
            usage_metadata=make_mock_usage_metadata(
                prompt_token_count=10,
                candidates_token_count=5,
                total_token_count=15,
            ),
        )
        # Simulate final chunk with cumulative counts
        value = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([make_mock_part(text="")]))],
            usage_metadata=make_mock_usage_metadata(
                prompt_token_count=10,  # Same prompt count
                candidates_token_count=20,  # Final cumulative count
                total_token_count=30,
            ),
        )

        result = google_genai_gemini_accumulator(acc, value)

        # Should be replaced, not summed (not 10+10=20, 5+20=25, 15+30=45)
        assert result.usage_metadata.prompt_token_count == 10
        assert result.usage_metadata.candidates_token_count == 20
        assert result.usage_metadata.total_token_count == 30

    def test_thoughts_token_count_tracked(self) -> None:
        """Test that thoughts_token_count is tracked for thinking models."""
        acc = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([make_mock_part(text="")]))],
            usage_metadata=make_mock_usage_metadata(
                prompt_token_count=10,
                candidates_token_count=5,
                total_token_count=15,
            ),
        )
        value = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([make_mock_part(text="")]))],
            usage_metadata=make_mock_usage_metadata(
                prompt_token_count=10,
                candidates_token_count=100,
                total_token_count=110,
                thoughts_token_count=80,  # Thinking tokens
            ),
        )

        result = google_genai_gemini_accumulator(acc, value)

        assert result.usage_metadata.thoughts_token_count == 80

    def test_thinking_model_content_by_type(self) -> None:
        """Test that thinking and response content are accumulated separately.

        Thinking models can return parts with thought=True (thinking content)
        and thought=False/None (response content). These should not overwrite
        each other.
        """
        # First chunk with thinking content
        thought_part = make_mock_part(text="Let me think...", thought=True)
        acc = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([thought_part]))],
            usage_metadata=make_mock_usage_metadata(),
        )

        # Second chunk with response content (different thought type)
        response_part = make_mock_part(text="The answer is", thought=False)
        value = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([response_part]))],
            usage_metadata=make_mock_usage_metadata(),
        )

        result = google_genai_gemini_accumulator(acc, value)

        # Both parts should be present, not overwritten
        parts = result.candidates[0].content.parts
        assert len(parts) == 2
        assert parts[0].text == "Let me think..."
        assert parts[0].thought is True
        assert parts[1].text == "The answer is"
        assert parts[1].thought is False

    def test_thinking_content_accumulated_together(self) -> None:
        """Test that multiple chunks of thinking content are accumulated."""
        thought_part1 = make_mock_part(text="Step 1: ", thought=True)
        acc = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([thought_part1]))],
            usage_metadata=make_mock_usage_metadata(),
        )

        thought_part2 = make_mock_part(text="analyze the problem", thought=True)
        value = make_mock_response(
            candidates=[make_mock_candidate(make_mock_content([thought_part2]))],
            usage_metadata=make_mock_usage_metadata(),
        )

        result = google_genai_gemini_accumulator(acc, value)

        parts = result.candidates[0].content.parts
        assert len(parts) == 1
        assert parts[0].text == "Step 1: analyze the problem"
        assert parts[0].thought is True


class TestGoogleGenaiGeminiPostprocessInputs:
    """Tests for google_genai_gemini_postprocess_inputs function."""

    def test_extracts_model_name(self) -> None:
        """Test that model name is extracted from self._model."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"

        inputs = {"self": mock_self}
        result = google_genai_gemini_postprocess_inputs(inputs)

        assert result["model"] == "gemini-2.0-flash"

    def test_extracts_system_instruction(self) -> None:
        """Test that system_instruction is extracted from config."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"

        mock_config = MagicMock()
        mock_config.system_instruction = "You are a helpful assistant."

        inputs = {"self": mock_self, "config": mock_config}
        result = google_genai_gemini_postprocess_inputs(inputs)

        assert result["system_instruction"] == "You are a helpful assistant."

    def test_no_system_instruction_when_not_present(self) -> None:
        """Test that system_instruction is not added when not in config."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"

        mock_config = MagicMock(spec=[])  # No system_instruction attribute

        inputs = {"self": mock_self, "config": mock_config}
        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result

    def test_no_system_instruction_when_none(self) -> None:
        """Test that system_instruction is not added when it's None."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"

        mock_config = MagicMock()
        mock_config.system_instruction = None

        inputs = {"self": mock_self, "config": mock_config}
        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result


class TestGoogleGenaiGeminiOnFinish:
    """Tests for google_genai_gemini_on_finish function."""

    def test_raises_without_model_name(self) -> None:
        """Test that ValueError is raised when model name is missing."""
        mock_call = MagicMock()
        mock_call.inputs = {}

        with pytest.raises(ValueError, match="Unknown model type"):
            google_genai_gemini_on_finish(mock_call, None)

    def test_basic_usage_tracking(self) -> None:
        """Test that basic usage metadata is tracked."""
        mock_call = MagicMock()
        mock_call.inputs = {"model": "gemini-2.0-flash"}
        mock_call.summary = {}

        mock_output = MagicMock()
        mock_output.usage_metadata.prompt_token_count = 10
        mock_output.usage_metadata.candidates_token_count = 20
        mock_output.usage_metadata.total_token_count = 30
        del mock_output.usage_metadata.thoughts_token_count

        google_genai_gemini_on_finish(mock_call, mock_output)

        usage = mock_call.summary["usage"]["gemini-2.0-flash"]
        assert usage["requests"] == 1
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30
        assert "thoughts_tokens" not in usage

    def test_thoughts_tokens_included_for_thinking_models(self) -> None:
        """Test that thoughts_tokens is included for thinking models."""
        mock_call = MagicMock()
        mock_call.inputs = {"model": "gemini-2.0-flash-thinking-exp"}
        mock_call.summary = {}

        mock_output = MagicMock()
        mock_output.usage_metadata.prompt_token_count = 10
        mock_output.usage_metadata.candidates_token_count = 100
        mock_output.usage_metadata.total_token_count = 110
        mock_output.usage_metadata.thoughts_token_count = 80

        google_genai_gemini_on_finish(mock_call, mock_output)

        usage = mock_call.summary["usage"]["gemini-2.0-flash-thinking-exp"]
        assert usage["requests"] == 1
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 100
        assert usage["total_tokens"] == 110
        assert usage["thoughts_tokens"] == 80
