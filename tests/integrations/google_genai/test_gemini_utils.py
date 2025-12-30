"""Unit tests for the Google GenAI Gemini utility functions."""

from unittest.mock import MagicMock

from weave.integrations.google_genai.gemini_utils import (
    google_genai_gemini_accumulator,
    google_genai_gemini_on_finish,
    google_genai_gemini_postprocess_inputs,
)


class TestGoogleGenaiGeminiPostprocessInputs:
    def test_extracts_model_name(self):
        """Test that model name is extracted from self._model."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"
        inputs = {"self": mock_self}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert result["model"] == "gemini-2.0-flash"

    def test_extracts_system_instruction_from_config(self):
        """Test that system_instruction is extracted from config and surfaced at top level."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"
        mock_config = MagicMock()
        mock_config.system_instruction = "You are a helpful assistant."
        inputs = {"self": mock_self, "config": mock_config}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert result["system_instruction"] == "You are a helpful assistant."

    def test_handles_missing_system_instruction(self):
        """Test that missing system_instruction doesn't cause errors."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"
        mock_config = MagicMock(spec=[])  # No system_instruction attribute
        inputs = {"self": mock_self, "config": mock_config}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result

    def test_handles_none_config(self):
        """Test that None config doesn't cause errors."""
        mock_self = MagicMock()
        mock_self._model = "gemini-2.0-flash"
        inputs = {"self": mock_self, "config": None}

        result = google_genai_gemini_postprocess_inputs(inputs)

        assert "system_instruction" not in result


class TestGoogleGenaiGeminiOnFinish:
    def test_tracks_basic_token_counts(self):
        """Test that basic token counts are tracked in usage summary."""
        mock_call = MagicMock()
        mock_call.inputs = {"model": "gemini-2.0-flash"}
        mock_call.summary = {}

        mock_output = MagicMock()
        mock_output.usage_metadata.prompt_token_count = 10
        mock_output.usage_metadata.candidates_token_count = 20
        mock_output.usage_metadata.total_token_count = 30

        google_genai_gemini_on_finish(mock_call, mock_output)

        usage = mock_call.summary["usage"]["gemini-2.0-flash"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 20
        assert usage["total_tokens"] == 30
        assert usage["requests"] == 1

    def test_tracks_thinking_tokens(self):
        """Test that thinking tokens are tracked for thinking models."""
        mock_call = MagicMock()
        mock_call.inputs = {"model": "gemini-2.0-flash-thinking-exp"}
        mock_call.summary = {}

        mock_output = MagicMock()
        mock_output.usage_metadata.prompt_token_count = 10
        mock_output.usage_metadata.candidates_token_count = 20
        mock_output.usage_metadata.total_token_count = 30
        mock_output.usage_metadata.thoughts_token_count = 100

        google_genai_gemini_on_finish(mock_call, mock_output)

        usage = mock_call.summary["usage"]["gemini-2.0-flash-thinking-exp"]
        assert usage["thoughts_tokens"] == 100

    def test_handles_missing_thinking_tokens(self):
        """Test that missing thinking tokens don't cause errors."""
        mock_call = MagicMock()
        mock_call.inputs = {"model": "gemini-2.0-flash"}
        mock_call.summary = {}

        mock_output = MagicMock()
        mock_output.usage_metadata.prompt_token_count = 10
        mock_output.usage_metadata.candidates_token_count = 20
        mock_output.usage_metadata.total_token_count = 30
        # No thoughts_token_count attribute
        del mock_output.usage_metadata.thoughts_token_count

        google_genai_gemini_on_finish(mock_call, mock_output)

        usage = mock_call.summary["usage"]["gemini-2.0-flash"]
        assert "thoughts_tokens" not in usage


class TestGoogleGenaiGeminiAccumulator:
    def _create_mock_response(
        self,
        text="",
        prompt_tokens=None,
        candidates_tokens=None,
        total_tokens=None,
        cached_tokens=None,
        thoughts_tokens=None,
        thought=False,
    ):
        """Helper to create mock GenerateContentResponse objects."""
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = text
        mock_part.thought = thought

        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]

        mock_response.usage_metadata.prompt_token_count = prompt_tokens
        mock_response.usage_metadata.candidates_token_count = candidates_tokens
        mock_response.usage_metadata.total_token_count = total_tokens
        mock_response.usage_metadata.cached_content_token_count = cached_tokens

        if thoughts_tokens is not None:
            mock_response.usage_metadata.thoughts_token_count = thoughts_tokens
        else:
            # Remove the attribute to simulate non-thinking models
            del mock_response.usage_metadata.thoughts_token_count

        return mock_response

    def test_returns_value_when_acc_is_none(self):
        """Test that first chunk becomes the accumulator."""
        value = self._create_mock_response(text="Hello")
        result = google_genai_gemini_accumulator(None, value)
        assert result is value

    def test_token_counts_are_replaced_not_summed(self):
        """Test that token counts are replaced (cumulative) not summed.

        The Gemini API returns cumulative token counts during streaming,
        so we should use the latest value, not sum them.
        """
        acc = self._create_mock_response(
            text="Hello",
            prompt_tokens=5,
            candidates_tokens=2,
            total_tokens=7,
        )
        value = self._create_mock_response(
            text=" world",
            prompt_tokens=5,  # Same prompt tokens (cumulative)
            candidates_tokens=4,  # Increased (cumulative)
            total_tokens=9,  # Increased (cumulative)
        )

        result = google_genai_gemini_accumulator(acc, value)

        # Token counts should be replaced, not summed
        assert result.usage_metadata.prompt_token_count == 5
        assert result.usage_metadata.candidates_token_count == 4
        assert result.usage_metadata.total_token_count == 9

    def test_text_is_accumulated(self):
        """Test that text content is accumulated across chunks."""
        acc = self._create_mock_response(text="Hello")
        value = self._create_mock_response(text=" world")

        result = google_genai_gemini_accumulator(acc, value)

        assert result.candidates[0].content.parts[0].text == "Hello world"

    def test_thought_and_response_parts_accumulated_separately(self):
        """Test that thought parts and response parts don't overwrite each other.

        When streaming with thinking models, parts may arrive at the same index
        but with different 'thought' values. These should be accumulated separately.
        """
        # First chunk: thought part
        acc = self._create_mock_response(text="Thinking...", thought=True)

        # Second chunk: response part (same index, different thought value)
        value = self._create_mock_response(text="Response", thought=False)

        result = google_genai_gemini_accumulator(acc, value)

        # Both parts should be preserved
        parts = result.candidates[0].content.parts
        assert len(parts) == 2

        # Find thought and response parts
        thought_text = None
        response_text = None
        for part in parts:
            if getattr(part, "thought", False):
                thought_text = part.text
            else:
                response_text = part.text

        assert thought_text == "Thinking..."
        assert response_text == "Response"

    def test_thought_parts_accumulated_together(self):
        """Test that multiple thought chunks are accumulated together."""
        acc = self._create_mock_response(text="Thinking ", thought=True)
        value = self._create_mock_response(text="more...", thought=True)

        result = google_genai_gemini_accumulator(acc, value)

        parts = result.candidates[0].content.parts
        assert len(parts) == 1
        assert parts[0].text == "Thinking more..."

    def test_handles_thinking_token_counts(self):
        """Test that thinking token counts are properly tracked."""
        acc = self._create_mock_response(
            text="Hello",
            prompt_tokens=5,
            candidates_tokens=2,
            total_tokens=7,
            thoughts_tokens=50,
        )
        value = self._create_mock_response(
            text=" world",
            prompt_tokens=5,
            candidates_tokens=4,
            total_tokens=9,
            thoughts_tokens=100,  # Cumulative
        )

        result = google_genai_gemini_accumulator(acc, value)

        assert result.usage_metadata.thoughts_token_count == 100

    def test_handles_cached_token_counts(self):
        """Test that cached content token counts are properly handled."""
        acc = self._create_mock_response(
            text="Hello",
            prompt_tokens=5,
            candidates_tokens=2,
            total_tokens=7,
            cached_tokens=3,
        )
        value = self._create_mock_response(
            text=" world",
            prompt_tokens=5,
            candidates_tokens=4,
            total_tokens=9,
            cached_tokens=3,  # Same (cumulative)
        )

        result = google_genai_gemini_accumulator(acc, value)

        assert result.usage_metadata.cached_content_token_count == 3
