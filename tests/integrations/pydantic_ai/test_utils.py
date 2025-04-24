"""
Unit tests for PydanticAI utility functions.

This module contains tests for various utility functions in the PydanticAI integration,
including event handling, usage tracking, tool call processing, and OpenTelemetry span
exporting. The tests verify that spans are correctly processed and that attributes
are properly transformed according to Weave's internal schema.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider

from weave.integrations.pydantic_ai.utils import (
    PydanticAISpanExporter,
    dicts_to_events,
    handle_events,
    handle_tool_call,
    handle_usage,
    map_events_to_prompt_completion,
)


def test_dicts_to_events_with_empty_list() -> None:
    """
    Test that an empty list of dictionaries returns an empty list of events.

    This test verifies that the dicts_to_events function correctly handles
    an empty input list and returns an empty list of events.
    """
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        events = dicts_to_events([], span)  # type: ignore
        assert events == []


def test_dicts_to_events_with_valid_events() -> None:
    """
    Test that valid event dictionaries are converted to Event objects.

    This test verifies that dicts_to_events correctly converts dictionaries
    with event data into OpenTelemetry Event objects with proper names and attributes.
    It tests three cases:
    1. Dictionary with "event.name" key
    2. Dictionary with "name" key
    3. Dictionary with neither, which should use a default name
    """
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        event_dicts = [
            {"event.name": "test_event1", "attr1": "value1"},
            {"name": "test_event2", "attr2": "value2"},
            {"attr3": "value3"},
        ]
        events = dicts_to_events(event_dicts, span)  # type: ignore

        assert len(events) == 3
        assert isinstance(events[0], Event)
        assert events[0].name == "test_event1"
        assert events[0].attributes == {"attr1": "value1"}
        assert events[1].name == "test_event2"
        assert events[1].attributes == {"attr2": "value2"}
        assert events[2].name == "event"
        assert events[2].attributes == {"attr3": "value3"}


def test_handle_events_no_events_in_attrs() -> None:
    """
    Test handling when no events are present in attributes.

    This test verifies that when the specified event key is not in the attributes
    dictionary, the span is returned unchanged without modifications.
    """
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        attrs: dict[str, Any] = {"key1": "value1"}
        new_span = handle_events("events", attrs, span)
        assert new_span is span
        assert attrs == {"key1": "value1"}


def test_handle_events_with_string_events() -> None:
    """
    Test that string events are parsed as JSON.

    This test verifies that when events are provided as a JSON string in the
    attributes dictionary, they are correctly parsed and added to the span
    as Event objects, and the original event key is removed from attributes.
    """
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        attrs: dict[str, Any] = {
            "events": '[{"name": "test_event", "attr1": "value1"}]'
        }
        new_span = handle_events("events", attrs, span)
        assert new_span is span
        assert "events" not in attrs
        assert hasattr(span, "_events")
        assert len(span._events) == 1
        assert span._events[0].name == "test_event"
        assert span._events[0].attributes == {"attr1": "value1"}


def test_map_events_to_prompt_completion_no_events() -> None:
    """
    Test mapping with no events present.

    This test verifies that when no events are present on the span, the
    map_events_to_prompt_completion function returns the span unchanged
    without adding any new attributes.
    """
    tracer_provider = TracerProvider()
    tracer = tracer_provider.get_tracer(__name__)
    with tracer.start_span("test") as span:
        new_span = map_events_to_prompt_completion(span)
        assert new_span is span
        assert span._attributes == {}


def test_map_events_to_prompt_completion_with_message_events() -> None:
    """
    Test mapping message events to prompt and completion attributes.

    This test verifies that when the span contains system, user, and assistant
    message events, they are correctly mapped to gen_ai.prompt and gen_ai.completion
    attributes on the span.
    """
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
        assert "You are a helpful assistant" in span._attributes["gen_ai.prompt"]
        assert "Hello" in span._attributes["gen_ai.prompt"]
        assert "Hi there!" in span._attributes["gen_ai.completion"]


def test_handle_usage() -> None:
    """
    Test transformation of usage tokens.

    This test verifies that input and output tokens are correctly renamed to
    prompt and completion tokens in the span attributes for compatibility with
    Weave's internal schema.
    """
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


def test_handle_tool_call() -> None:
    """
    Test processing of tool call attributes.

    This test verifies that tool call attributes are correctly updated to match
    Weave's internal schema, including setting the input value, operation name,
    and display name for the tool call.
    """
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
def mock_otlp_exporter() -> Any:
    """
    Fixture that provides a mocked OTLPSpanExporter.

    This fixture patches the OTLPSpanExporter class from the pydantic_ai.utils
    module to avoid making real network calls during testing.
    """
    with patch("weave.integrations.pydantic_ai.utils.OTLPSpanExporter") as mock:
        yield mock


def test_pydantic_ai_span_exporter_export(mock_otlp_exporter: Any) -> None:
    """
    Test that spans are processed and exported correctly by PydanticAISpanExporter.

    This test verifies the complete flow of span processing in the exporter:
    1. Usage tokens are renamed appropriately
    2. Tool call attributes are updated correctly
    3. Events are mapped to prompt and completion attributes
    4. The processed span is passed to the underlying OTLP exporter
    """
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

        result = exporter.export([span])

        assert "gen_ai.usage.prompt_tokens" in span._attributes
        assert "gen_ai.usage.completion_tokens" in span._attributes
        assert "gen_ai.usage.input_tokens" not in span._attributes
        assert "gen_ai.usage.output_tokens" not in span._attributes
        assert span._attributes["input.value"] == '{"arg1": "value1"}'
        assert span._attributes["gen_ai.operation.name"] == "execute_tool"
        assert span._attributes["wandb.display_name"] == "calling tool: example_tool"
        assert "gen_ai.prompt" in span._attributes
        assert "gen_ai.completion" in span._attributes
        assert "System message" in span._attributes["gen_ai.prompt"]
        assert "User message" in span._attributes["gen_ai.prompt"]
        assert "Assistant response" in span._attributes["gen_ai.completion"]
        mock_otlp_exporter.return_value.export.assert_called_once_with([span])
        assert result == mock_otlp_exporter.return_value.export.return_value
