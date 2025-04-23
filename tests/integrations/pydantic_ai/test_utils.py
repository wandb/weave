import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace import Event
from weave.integrations.pydantic_ai.utils import (
    dicts_to_events,
    handle_events,
    map_events_to_prompt_completion,
    handle_usage,
    handle_tool_call,
    PydanticAISpanExporter,
)
from unittest.mock import MagicMock, patch
from opentelemetry.sdk.trace import ReadableSpan
import json


def test_dicts_to_events_with_empty_list():
    """Test that an empty list returns an empty list."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        events = dicts_to_events([], span)  # type: ignore
        assert events == []


def test_dicts_to_events_with_valid_events():
    """Test that valid event dicts are converted to Event objects."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        event_dicts = [
            {"event.name": "test_event1", "attr1": "value1"},
            {"name": "test_event2", "attr2": "value2"},
            {"attr3": "value3"},  # No name
        ]
        events = dicts_to_events(event_dicts, span)  # type: ignore

        assert len(events) == 3
        assert isinstance(events[0], Event)
        assert events[0].name == "test_event1"
        assert events[0].attributes == {"attr1": "value1"}

        assert events[1].name == "test_event2"
        assert events[1].attributes == {"attr2": "value2"}

        assert events[2].name == "event"  # Default name
        assert events[2].attributes == {"attr3": "value3"}


def test_handle_events_no_events_in_attrs():
    """Test that when no events are in attrs, span is returned unchanged."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        attrs = {"key1": "value1"}
        new_span = handle_events("events", attrs, span)

        assert new_span is span
        assert attrs == {"key1": "value1"}  # Unchanged


def test_handle_events_with_string_events():
    """Test that string events are parsed as JSON."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        attrs = {"events": '[{"name": "test_event", "attr1": "value1"}]'}
        new_span = handle_events("events", attrs, span)

        assert new_span is span
        assert "events" not in attrs  # Key is removed
        assert hasattr(span, "_events")
        assert len(span._events) == 1
        assert span._events[0].name == "test_event"
        assert span._events[0].attributes == {"attr1": "value1"}


def test_map_events_to_prompt_completion_no_events():
    """Test that when no events are present, span is returned unchanged."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        new_span = map_events_to_prompt_completion(span)

        assert new_span is span
        assert span._attributes == {}


def test_map_events_to_prompt_completion_with_message_events():
    """Test that message events are mapped to prompt and completion."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        # Add events to the span with attributes containing the required keys
        span._events = [
            Event(
                name="gen_ai.system.message",
                attributes={
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
            ),
            Event(
                name="gen_ai.user.message",
                attributes={"role": "user", "content": "Hello"},
            ),
            Event(
                name="gen_ai.choice",
                attributes={"role": "assistant", "content": "Hi there!"},
            ),
        ]
        span._attributes = {}

        new_span = map_events_to_prompt_completion(span)

        assert new_span is span
        assert "gen_ai.prompt" in span._attributes
        assert "gen_ai.completion" in span._attributes

        # Verify the prompt contains the system and user messages
        assert "You are a helpful assistant" in span._attributes["gen_ai.prompt"]
        assert "Hello" in span._attributes["gen_ai.prompt"]

        # Verify the completion contains the assistant message
        assert "Hi there!" in span._attributes["gen_ai.completion"]


def test_handle_usage():
    """Test that input and output tokens are renamed to prompt and completion tokens."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        span._attributes = {
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 50,
        }

        updated_span = handle_usage(span)

        assert "gen_ai.usage.input_tokens" not in updated_span._attributes
        assert "gen_ai.usage.output_tokens" not in updated_span._attributes
        assert updated_span._attributes["gen_ai.usage.prompt_tokens"] == 100
        assert updated_span._attributes["gen_ai.usage.completion_tokens"] == 50


def test_handle_tool_call():
    """Test that tool call attributes are updated correctly."""
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        span._attributes = {
            "gen_ai.tool.call.id": "12345",
            "tool_arguments": '{"arg1": "value1"}',
            "gen_ai.tool.name": "example_tool",
        }

        updated_span = handle_tool_call(span)

        assert updated_span._attributes["input.value"] == '{"arg1": "value1"}'
        assert updated_span._attributes["gen_ai.operation.name"] == "execute_tool"
        assert (
            updated_span._attributes["wandb.display_name"]
            == "calling tool: example_tool"
        )


@pytest.fixture
def mock_otlp_exporter():
    with patch("weave.integrations.pydantic_ai.utils.OTLPSpanExporter") as mock:
        yield mock


def test_pydantic_ai_span_exporter_export(mock_otlp_exporter):
    """Test that spans are processed and exported correctly."""
    with patch(
        "weave.integrations.pydantic_ai.utils.PydanticAISpanExporter.__init__",
        return_value=None,
    ):
        exporter = PydanticAISpanExporter()
        exporter._otlp_exporter = mock_otlp_exporter.return_value

        # Create a mock span
        span = MagicMock(spec=ReadableSpan)
        span._attributes = {
            "gen_ai.usage.input_tokens": 100,
            "gen_ai.usage.output_tokens": 50,
            "gen_ai.tool.call.id": "12345",
            "tool_arguments": '{"arg1": "value1"}',
            "gen_ai.tool.name": "example_tool",
            # Set the events as a JSON string to test the full flow
            "events": json.dumps(
                [
                    {
                        "name": "gen_ai.system.message",
                        "role": "system",
                        "content": "System message",
                    },
                    {
                        "name": "gen_ai.user.message",
                        "role": "user",
                        "content": "User message",
                    },
                    {
                        "name": "gen_ai.choice",
                        "role": "assistant",
                        "content": "Assistant response",
                    },
                ]
            ),
        }

        # Call export
        result = exporter.export([span])

        # Verify usage tokens are renamed
        assert "gen_ai.usage.prompt_tokens" in span._attributes
        assert "gen_ai.usage.completion_tokens" in span._attributes
        assert "gen_ai.usage.input_tokens" not in span._attributes
        assert "gen_ai.usage.output_tokens" not in span._attributes

        # Verify tool call attributes are updated
        assert span._attributes["input.value"] == '{"arg1": "value1"}'
        assert span._attributes["gen_ai.operation.name"] == "execute_tool"
        assert span._attributes["wandb.display_name"] == "calling tool: example_tool"

        # Verify events are mapped to prompt and completion
        assert "gen_ai.prompt" in span._attributes
        assert "gen_ai.completion" in span._attributes
        assert "System message" in span._attributes["gen_ai.prompt"]
        assert "User message" in span._attributes["gen_ai.prompt"]
        assert "Assistant response" in span._attributes["gen_ai.completion"]

        # Verify export call
        mock_otlp_exporter.return_value.export.assert_called_once_with([span])
        assert result == mock_otlp_exporter.return_value.export.return_value
