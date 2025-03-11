"""
A Weave integration for OpenAI Agents.

This module provides a TracingProcessor implementation that logs OpenAI
Agent traces and spans to Weave.
"""

from __future__ import annotations

import datetime
from typing import Any

from agents import tracing
from agents.tracing import add_trace_processor

import weave
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import get_weave_client


def _timestamp_from_maybe_iso(timestamp: str | None) -> float | None:
    """Convert an ISO timestamp string to a float timestamp."""
    if timestamp is None:
        return None
    return datetime.datetime.fromisoformat(timestamp).timestamp()


def _call_type(span: tracing.Span[Any]) -> str:
    """Determine the appropriate call type for a given OpenAI Agent span."""
    if span.span_data.type in ["agent", "handoff", "custom"]:
        return "task"
    elif span.span_data.type in ["function", "guardrail"]:
        return "tool"
    elif span.span_data.type in ["generation", "response"]:
        return "llm"
    else:
        return "task"


def _call_name(span: tracing.Span[Any]) -> str:
    """Determine the name for a given OpenAI Agent span."""
    if (
        isinstance(span.span_data, tracing.AgentSpanData)
        or isinstance(span.span_data, tracing.FunctionSpanData)
        or isinstance(span.span_data, tracing.GuardrailSpanData)
        or isinstance(span.span_data, tracing.CustomSpanData)
    ):
        return span.span_data.name
    elif isinstance(span.span_data, tracing.GenerationSpanData):
        return "Generation"
    elif isinstance(span.span_data, tracing.ResponseSpanData):
        return "Response"
    elif isinstance(span.span_data, tracing.HandoffSpanData):
        return "Handoff"
    else:
        return "Unknown"


def _maybe_timestamp_elapsed(end: str | None, start: str | None) -> float | None:
    """Calculate the elapsed time between two ISO timestamp strings."""
    if start is None or end is None:
        return None
    return (
        datetime.datetime.fromisoformat(end) - datetime.datetime.fromisoformat(start)
    ).total_seconds()


class WeaveTracingProcessor(tracing.TracingProcessor):
    """
    A TracingProcessor implementation that logs OpenAI Agent traces and spans to Weave.

    This processor captures different types of spans from OpenAI Agents (agent execution,
    function calls, LLM generations, etc.) and logs them to Weave as structured trace data.

    Args:
        parent_call: Optional Weave call to use as the parent for all traces.
            If None, the current call from the context will be used.
    """

    def __init__(
        self, parent_call: weave.trace.context.call_context.Call | None = None
    ):
        self._parent_call = parent_call
        # We'll track the data from traces and spans, but we won't create new calls
        self._trace_data: dict[str, dict[str, Any]] = {}
        self._trace_calls: dict[str, weave.trace.context.call_context.Call] = {}
        self._span_calls: dict[str, weave.trace.context.call_context.Call] = {}
        self._ended_traces: set[str] = set()
        # Track parent-child relationships between spans
        self._span_parents: dict[str, str] = {}  # span_id -> parent_span_id

    def on_trace_start(self, trace: tracing.Trace) -> None:
        """Called when a trace starts."""
        # Just collect metadata initially
        self._trace_data[trace.trace_id] = {
            "name": trace.name,
            "type": "task",
            # "started_at": trace.started_at,
            "metrics": {},
            "metadata": {},
        }

        # Get the current Weave client and create a call for this trace
        weave_client = get_weave_client()
        if weave_client is not None:
            # Create a call for this trace
            parent = self._parent_call or call_context.get_current_call()
            attributes = {"type": "task", "agent_trace_id": trace.trace_id}

            trace_call = weave_client.create_call(
                op="openai_agent_trace",
                inputs={"name": trace.name},
                parent=parent,
                attributes=attributes,
                display_name=trace.name,
            )

            # Store the call for later use
            self._trace_calls[trace.trace_id] = trace_call

    def on_trace_end(self, trace: tracing.Trace) -> None:
        """Called when a trace ends."""
        if trace.trace_id in self._trace_data:
            trace_data = self._trace_data[trace.trace_id]
            # trace_data["ended_at"] = trace.ended_at

            # Calculate duration if possible
            # if trace.started_at and trace.ended_at:
            #     duration = _maybe_timestamp_elapsed(trace.ended_at, trace.started_at)
            #     if duration is not None:
            #         trace_data["metrics"]["duration"] = duration

            # Mark as ended
            self._ended_traces.add(trace.trace_id)
            trace_data["status"] = "completed"

            # Finish the trace call
            if trace.trace_id in self._trace_calls:
                trace_call = self._trace_calls[trace.trace_id]
                weave_client = get_weave_client()
                if weave_client is not None:
                    # Update any metrics and metadata
                    output = {
                        "status": "completed",
                        "metrics": trace_data.get("metrics", {}),
                        "metadata": trace_data.get("metadata", {}),
                    }

                    # Add spans if present
                    for span_type in ["task_spans", "tool_spans", "llm_spans"]:
                        if span_type in trace_data:
                            output[span_type] = trace_data[span_type]

                    # Finish the call with the collected data
                    weave_client.finish_call(trace_call, output=output)

    def _agent_log_data(
        self, span: tracing.Span[tracing.AgentSpanData]
    ) -> dict[str, Any]:
        """Extract log data from an agent span."""
        return {
            "metadata": {
                "tools": span.span_data.tools,
                "handoffs": span.span_data.handoffs,
                "output_type": span.span_data.output_type,
            }
        }

    def _response_log_data(
        self, span: tracing.Span[tracing.ResponseSpanData]
    ) -> dict[str, Any]:
        """Extract log data from a response span."""
        data: dict[str, Any] = {}
        if span.span_data.input is not None:
            data["input"] = span.span_data.input
        if span.span_data.response is not None:
            data["output"] = span.span_data.response.output
        if span.span_data.response is not None:
            data["metadata"] = span.span_data.response.metadata or {}
            data["metadata"].update(
                span.span_data.response.model_dump(
                    exclude={"input", "output", "metadata", "usage"}
                )
            )

        data["metrics"] = {}
        # ttft = _maybe_timestamp_elapsed(span.ended_at, span.started_at)
        # if ttft is not None:
        #     data["metrics"]["time_to_first_token"] = ttft
        if (
            span.span_data.response is not None
            and span.span_data.response.usage is not None
        ):
            data["metrics"]["tokens"] = span.span_data.response.usage.total_tokens
            data["metrics"]["prompt_tokens"] = (
                span.span_data.response.usage.input_tokens
            )
            data["metrics"]["completion_tokens"] = (
                span.span_data.response.usage.output_tokens
            )

        return data

    def _function_log_data(
        self, span: tracing.Span[tracing.FunctionSpanData]
    ) -> dict[str, Any]:
        """Extract log data from a function span."""
        return {
            "input": span.span_data.input,
            "output": span.span_data.output,
        }

    def _handoff_log_data(
        self, span: tracing.Span[tracing.HandoffSpanData]
    ) -> dict[str, Any]:
        """Extract log data from a handoff span."""
        return {
            "metadata": {
                "from_agent": span.span_data.from_agent,
                "to_agent": span.span_data.to_agent,
            }
        }

    def _guardrail_log_data(
        self, span: tracing.Span[tracing.GuardrailSpanData]
    ) -> dict[str, Any]:
        """Extract log data from a guardrail span."""
        return {
            "metadata": {
                "triggered": span.span_data.triggered,
            }
        }

    def _generation_log_data(
        self, span: tracing.Span[tracing.GenerationSpanData]
    ) -> dict[str, Any]:
        """Extract log data from a generation span."""
        metrics = {}
        # ttft = _maybe_timestamp_elapsed(span.ended_at, span.started_at)
        # if ttft is not None:
        #     metrics["time_to_first_token"] = ttft
        if span.span_data.usage is not None:
            metrics["tokens"] = span.span_data.usage["total_tokens"]
            metrics["prompt_tokens"] = span.span_data.usage["prompt_tokens"]
            metrics["completion_tokens"] = span.span_data.usage["completion_tokens"]

        return {
            "input": span.span_data.input,
            "output": span.span_data.output,
            "metadata": {
                "model": span.span_data.model,
                "model_config": span.span_data.model_config,
            },
            "metrics": metrics,
        }

    def _custom_log_data(
        self, span: tracing.Span[tracing.CustomSpanData]
    ) -> dict[str, Any]:
        """Extract log data from a custom span."""
        return span.span_data.data

    def _log_data(self, span: tracing.Span[Any]) -> dict[str, Any]:
        """Extract the appropriate log data based on the span type."""
        if isinstance(span.span_data, tracing.AgentSpanData):
            return self._agent_log_data(span)
        elif isinstance(span.span_data, tracing.ResponseSpanData):
            return self._response_log_data(span)
        elif isinstance(span.span_data, tracing.FunctionSpanData):
            return self._function_log_data(span)
        elif isinstance(span.span_data, tracing.HandoffSpanData):
            return self._handoff_log_data(span)
        elif isinstance(span.span_data, tracing.GuardrailSpanData):
            return self._guardrail_log_data(span)
        elif isinstance(span.span_data, tracing.GenerationSpanData):
            return self._generation_log_data(span)
        elif isinstance(span.span_data, tracing.CustomSpanData):
            return self._custom_log_data(span)
        else:
            return {}

    def on_span_start(self, span: tracing.Span[Any]) -> None:
        """Called when a span starts."""
        # Add this span to its parent trace
        trace_id = span.trace_id
        if trace_id in self._trace_data:
            # Initialize spans list if it doesn't exist
            if "spans" not in self._trace_data[trace_id]:
                self._trace_data[trace_id]["spans"] = {}

            # Track the span data
            span_name = _call_name(span)
            span_type = _call_type(span)

            # Determine the parent span (if any)
            parent_span_id = None
            if hasattr(span, "parent_id") and span.parent_id:
                parent_span_id = span.parent_id
                self._span_parents[span.span_id] = parent_span_id

            self._trace_data[trace_id]["spans"][span.span_id] = {
                "name": span_name,
                "type": span_type,
                "parent_span_id": parent_span_id,
                # "started_at": span.started_at,
                "metadata": {},
                "metrics": {},
            }

            # Create a call for this span
            # Parent call can be either:
            # 1. The parent span's call (if this span has a parent span)
            # 2. The trace call (if this is a top-level span)
            parent_call = None
            if parent_span_id and parent_span_id in self._span_calls:
                # This is a child span of another span
                parent_call = self._span_calls[parent_span_id]
            elif trace_id in self._trace_calls:
                # This is a top-level span directly under the trace
                parent_call = self._trace_calls[trace_id]

            if parent_call:
                weave_client = get_weave_client()

                if weave_client is not None:
                    # Create attributes based on span type
                    attributes = {
                        "type": span_type,
                        "agent_span_id": span.span_id,
                        "agent_trace_id": trace_id,
                    }
                    if parent_span_id:
                        attributes["parent_span_id"] = parent_span_id

                    # Create a call for this span
                    span_call = weave_client.create_call(
                        op=f"openai_agent_{span_type}",
                        inputs={"name": span_name},
                        parent=parent_call,
                        attributes=attributes,
                        display_name=span_name,
                    )

                    # Store the call for later use
                    self._span_calls[span.span_id] = span_call

    def on_span_end(self, span: tracing.Span[Any]) -> None:
        """Called when a span ends."""
        trace_id = span.trace_id
        if trace_id in self._trace_data and "spans" in self._trace_data[trace_id]:
            if span.span_id in self._trace_data[trace_id]["spans"]:
                # Update the span data
                span_data = self._trace_data[trace_id]["spans"][span.span_id]
                # span_data["ended_at"] = span.ended_at

                # Add a status field to the span
                span_data["status"] = "completed"

                # Add log data
                log_data = self._log_data(span)
                span_data.update(log_data)

                # Add error if present
                if span.error:
                    span_data["error"] = span.error
                    span_data["status"] = "error"

                # Calculate duration if possible
                # if span.started_at and span.ended_at:
                #     duration = _maybe_timestamp_elapsed(span.ended_at, span.started_at)
                #     if duration is not None:
                #         span_data["metrics"]["duration"] = duration

                # Organize the spans hierarchically in the trace data
                trace_data = self._trace_data[trace_id]

                # Ensure this span is tracked in the appropriate spans collection
                span_type = span_data["type"]
                if f"{span_type}_spans" not in trace_data:
                    trace_data[f"{span_type}_spans"] = []

                # Check if this span is already in the list
                span_exists = False
                for i, existing_span in enumerate(
                    trace_data.get(f"{span_type}_spans", [])
                ):
                    if existing_span.get("agent_span_id") == span.span_id:
                        # Update the existing span
                        trace_data[f"{span_type}_spans"][i] = span_data
                        span_exists = True
                        break

                if not span_exists:
                    # Add the span_id to help with identification
                    span_data["agent_span_id"] = span.span_id
                    trace_data[f"{span_type}_spans"].append(span_data)

                # Finish the span call if it exists
                if span.span_id in self._span_calls:
                    span_call = self._span_calls[span.span_id]
                    weave_client = get_weave_client()

                    if weave_client is not None:
                        # Prepare output data
                        output = {
                            "status": span_data["status"],
                            "type": span_data["type"],
                            "name": span_data["name"],
                        }

                        # Add parent_span_id if present
                        if (
                            "parent_span_id" in span_data
                            and span_data["parent_span_id"]
                        ):
                            output["parent_span_id"] = span_data["parent_span_id"]

                        # Add input/output if present
                        if "input" in span_data:
                            output["input"] = span_data["input"]
                        if "output" in span_data:
                            output["output"] = span_data["output"]

                        # Add metrics and metadata
                        output["metrics"] = span_data.get("metrics", {})
                        output["metadata"] = span_data.get("metadata", {})

                        # Build a nested structure of child spans if this is an agent span
                        if (
                            span_type == "task"
                            and "agent" in span_data.get("name", "").lower()
                        ):
                            # Find all child spans for this agent span
                            child_spans = []
                            for child_span_id, parent_id in self._span_parents.items():
                                if (
                                    parent_id == span.span_id
                                    and child_span_id
                                    in self._trace_data[trace_id]["spans"]
                                ):
                                    child_span_data = self._trace_data[trace_id][
                                        "spans"
                                    ][child_span_id]
                                    child_spans.append(child_span_data)

                            if child_spans:
                                output["child_spans"] = child_spans

                        # Finish the call with all the collected data
                        weave_client.finish_call(span_call, output=output)

                # If the trace is complete, update its call too with the properly organized data
                if trace_id in self._ended_traces and trace_id in self._trace_calls:
                    trace_call = self._trace_calls[trace_id]
                    weave_client = get_weave_client()

                    if weave_client is not None:
                        # Update the trace call with the latest data
                        output = {
                            "status": "completed",
                            "metrics": trace_data.get("metrics", {}),
                            "metadata": trace_data.get("metadata", {}),
                        }

                        # Add all span types with hierarchical organization
                        for span_type_key in ["task_spans", "tool_spans", "llm_spans"]:
                            if span_type_key in trace_data:
                                # Organize spans hierarchically
                                hierarchical_spans = []

                                # First get top-level spans (those without parents or with parents outside this trace)
                                for span_data in trace_data[span_type_key]:
                                    if (
                                        not span_data.get("parent_span_id")
                                        or span_data["parent_span_id"]
                                        not in self._trace_data[trace_id]["spans"]
                                    ):
                                        hierarchical_spans.append(span_data)

                                output[span_type_key] = hierarchical_spans

                        # Update the trace call
                        weave_client.finish_call(trace_call, output=output)

    def shutdown(self) -> None:
        """Called when the application stops."""
        # Final update for any traces that haven't been fully processed
        weave_client = get_weave_client()
        if weave_client is not None:
            for trace_id, trace_data in self._trace_data.items():
                if trace_id in self._trace_calls:
                    trace_call = self._trace_calls[trace_id]

                    # Set status based on whether it ended normally
                    status = (
                        "completed" if trace_id in self._ended_traces else "interrupted"
                    )
                    trace_data["status"] = status

                    # Prepare output with all the accumulated data
                    output = {
                        "status": status,
                        "metrics": trace_data.get("metrics", {}),
                        "metadata": trace_data.get("metadata", {}),
                    }

                    # Add all span types
                    for span_type in ["task_spans", "tool_spans", "llm_spans"]:
                        if span_type in trace_data:
                            output[span_type] = trace_data[span_type]

                    # Finish the call
                    weave_client.finish_call(trace_call, output=output)

            # Also close any span calls that weren't properly finished
            for span_id, span_call in self._span_calls.items():
                # Only process span calls that haven't been finished
                if not hasattr(span_call, "ended_at") or span_call.ended_at is None:
                    weave_client.finish_call(
                        span_call, output={"status": "interrupted"}
                    )

    def force_flush(self) -> None:
        """Forces an immediate flush of all queued spans/traces."""
        # Similar to shutdown, but we mark things as force_flushed
        weave_client = get_weave_client()
        if weave_client is not None:
            for trace_id, trace_data in self._trace_data.items():
                if trace_id in self._trace_calls:
                    trace_call = self._trace_calls[trace_id]

                    # Set status
                    status = (
                        "completed"
                        if trace_id in self._ended_traces
                        else "force_flushed"
                    )
                    trace_data["status"] = status

                    # Prepare output with all the accumulated data
                    output = {
                        "status": status,
                        "metrics": trace_data.get("metrics", {}),
                        "metadata": trace_data.get("metadata", {}),
                    }

                    # Add all span types
                    for span_type in ["task_spans", "tool_spans", "llm_spans"]:
                        if span_type in trace_data:
                            output[span_type] = trace_data[span_type]

                    # Finish the call
                    weave_client.finish_call(trace_call, output=output)


def install(
    parent_call: weave.trace.context.call_context.Call | None = None,
) -> WeaveTracingProcessor:
    """
    Install the Weave tracing processor for OpenAI Agents.

    This function creates a WeaveTracingProcessor and registers it with
    the OpenAI Agents tracing system.

    Args:
        parent_call: Optional Weave call to use as the parent for all traces.
            If None, the current call from the context will be used.

    Returns:
        The installed WeaveTracingProcessor instance.
    """
    processor = WeaveTracingProcessor(parent_call)
    add_trace_processor(processor)
    return processor
