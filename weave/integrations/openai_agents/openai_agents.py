"""
A Weave integration for OpenAI Agents.

This module provides a TracingProcessor implementation that logs OpenAI
Agent traces and spans to Weave.
"""

from __future__ import annotations

from typing import Any, TypedDict

from weave.integrations.patcher import NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.context import call_context
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.weave_client import Call

_openai_agents_patcher: OpenAIAgentsPatcher | None = None


try:
    from agents import tracing
    from agents.tracing import TracingProcessor
except ImportError:

    class TracingProcessor: ...  # type: ignore[no-redef]


def _call_type(span: tracing.Span[Any]) -> str:
    """Determine the appropriate call type for a given OpenAI Agent span."""
    return span.span_data.type or "task"


def _call_name(span: tracing.Span[Any]) -> str:
    """Determine the name for a given OpenAI Agent span."""
    if name := getattr(span.span_data, "name", None):
        return name
    elif isinstance(span.span_data, tracing.GenerationSpanData):
        return "Generation"
    elif isinstance(span.span_data, tracing.ResponseSpanData):
        return "Response"
    elif isinstance(span.span_data, tracing.HandoffSpanData):
        return "Handoff"
    else:
        return "Unknown"


class WeaveDataDict(TypedDict):
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any]
    metrics: dict[str, Any]
    error: dict[str, Any] | None


class WeaveTracingProcessor(TracingProcessor):  # pyright: ignore[reportGeneralTypeIssues]
    """
    A TracingProcessor implementation that logs OpenAI Agent traces and spans to Weave.

    This processor captures different types of spans from OpenAI Agents (agent execution,
    function calls, LLM generations, etc.) and logs them to Weave as structured trace data.
    Child spans are logged as separate calls but not redundantly included in the parent trace data.
    """

    def __init__(self) -> None:
        self._trace_data: dict[str, dict[str, Any]] = {}
        self._trace_calls: dict[str, call_context.Call] = {}
        self._span_calls: dict[str, call_context.Call] = {}
        self._ended_traces: set[str] = set()
        self._span_parents: dict[str, str] = {}

    def on_trace_start(self, trace: tracing.Trace) -> None:
        """Called when a trace starts."""
        # Set up basic trace data
        self._trace_data[trace.trace_id] = {
            "name": trace.name,
            "type": "task",
            "metrics": {},
            "metadata": {},
        }

        # Create a call for this trace
        wc = require_weave_client()
        trace_call = wc.create_call(
            op="openai_agent_trace",
            inputs={"name": trace.name},
            parent=call_context.get_current_call(),
            attributes={"type": "task", "agent_trace_id": trace.trace_id},
            display_name=trace.name,
        )
        self._trace_calls[trace.trace_id] = trace_call

    def on_trace_end(self, trace: tracing.Trace) -> None:
        """Called when a trace ends."""
        tid = trace.trace_id
        if tid not in self._trace_data:
            return
        if tid not in self._trace_calls:
            return

        trace_data = self._trace_data[tid]
        self._ended_traces.add(tid)

        # Finish the trace call
        output = {
            "status": "completed",
            "metrics": trace_data.get("metrics", {}),
            "metadata": trace_data.get("metadata", {}),
        }
        wc = require_weave_client()
        wc.finish_call(self._trace_calls[tid], output=output)

    def _agent_log_data(
        self, span: tracing.Span[tracing.AgentSpanData]
    ) -> WeaveDataDict:
        """Extract log data from an agent span."""
        return WeaveDataDict(
            inputs={},
            outputs={},
            metadata={
                "tools": span.span_data.tools,
                "handoffs": span.span_data.handoffs,
                "output_type": span.span_data.output_type,
            },
            metrics={},
            error=None,
        )

    def _response_log_data(
        self, span: tracing.Span[tracing.ResponseSpanData]
    ) -> WeaveDataDict:
        """Extract log data from a response span."""
        inputs = {}
        outputs = {}
        metadata: dict[str, Any] = {}
        metrics: dict[str, Any] = {}

        # Add input if available
        if span.span_data.input is not None:
            inputs["input"] = span.span_data.input

        # Extract output and other details from response
        if span.span_data.response is not None:
            # Just get the plain output value
            outputs["output"] = span.span_data.response.output

            # All other data goes into metadata
            metadata = span.span_data.response.metadata or {}

            # Add all other response fields to metadata
            additional_fields = span.span_data.response.model_dump(
                exclude={"input", "output", "metadata", "usage"}
            )
            metadata.update(additional_fields)

            # Add usage data to metrics if available
            if span.span_data.response.usage is not None:
                usage = span.span_data.response.usage
                metrics = {
                    "tokens": usage.total_tokens,
                    "prompt_tokens": usage.input_tokens,
                    "completion_tokens": usage.output_tokens,
                }

        return WeaveDataDict(
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
            metrics=metrics,
            error=None,
        )

    def _function_log_data(
        self, span: tracing.Span[tracing.FunctionSpanData]
    ) -> WeaveDataDict:
        """Extract log data from a function span."""
        return WeaveDataDict(
            inputs={"input": span.span_data.input},
            outputs={"output": span.span_data.output},
            metadata={},
            metrics={},
            error=None,
        )

    def _handoff_log_data(
        self, span: tracing.Span[tracing.HandoffSpanData]
    ) -> WeaveDataDict:
        """Extract log data from a handoff span."""
        return WeaveDataDict(
            inputs={},
            outputs={},
            metadata={
                "from_agent": span.span_data.from_agent,
                "to_agent": span.span_data.to_agent,
            },
            metrics={},
            error=None,
        )

    def _guardrail_log_data(
        self, span: tracing.Span[tracing.GuardrailSpanData]
    ) -> WeaveDataDict:
        """Extract log data from a guardrail span."""
        return WeaveDataDict(
            inputs={},
            outputs={},
            metadata={"triggered": span.span_data.triggered},
            metrics={},
            error=None,
        )

    def _generation_log_data(
        self, span: tracing.Span[tracing.GenerationSpanData]
    ) -> WeaveDataDict:
        """Extract log data from a generation span."""
        return WeaveDataDict(
            inputs={"input": span.span_data.input},
            outputs={"output": span.span_data.output},
            metadata={
                "model": span.span_data.model,
                "model_config": span.span_data.model_config,
            },
            metrics={
                "tokens": span.span_data.usage.get("total_tokens"),
                "prompt_tokens": span.span_data.usage.get("prompt_tokens"),
                "completion_tokens": span.span_data.usage.get("completion_tokens"),
            },
            error=None,
        )

    def _custom_log_data(
        self, span: tracing.Span[tracing.CustomSpanData]
    ) -> WeaveDataDict:
        """Extract log data from a custom span."""
        # Prepare fields
        inputs = {}
        outputs = {}
        metadata: dict[str, Any] = {}
        metrics: dict[str, Any] = {}

        # Extract data from the custom span
        custom_data = span.span_data.data

        # Map custom data to the appropriate fields if possible
        if "input" in custom_data:
            inputs["input"] = custom_data["input"]

        if "output" in custom_data:
            outputs["output"] = custom_data["output"]

        if "metadata" in custom_data:
            metadata = custom_data["metadata"]

        if "metrics" in custom_data:
            metrics = custom_data["metrics"]

        # Add any remaining fields to metadata
        for key, value in custom_data.items():
            if key not in ["input", "output", "metadata", "metrics"]:
                metadata[key] = value

        return WeaveDataDict(
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
            metrics=metrics,
            error=None,
        )

    def _log_data(self, span: tracing.Span[Any]) -> WeaveDataDict:
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
            return WeaveDataDict(
                inputs={},
                outputs={},
                metadata={},
                metrics={},
                error=None,
            )

    def _get_parent_call(self, span: tracing.Span[Any]) -> Call | None:
        """Helper method to determine the parent call for a span."""
        trace_id = span.trace_id
        parent_span_id = getattr(span, "parent_id", None)

        # Child span
        if parent_span_id is not None and (
            call := self._span_calls.get(parent_span_id)
        ):
            return call

        # Trace root
        if call := self._trace_calls.get(trace_id):
            return call

        # Should not reach here, but kept for completeness
        return None

    def on_span_start(self, span: tracing.Span[Any]) -> None:
        """Called when a span starts."""
        # For Response spans, we'll defer call creation until on_span_end when we have input data
        if isinstance(span.span_data, tracing.ResponseSpanData):
            return

        # Spans must have a parent (either another span or the trace root)
        if not self._get_parent_call(span):
            return

        # Spans must be part of a trace
        tid = span.trace_id
        if tid not in self._trace_data:
            return

        span_name = _call_name(span)
        span_type = _call_type(span)
        parent_call = self._get_parent_call(span)

        wc = require_weave_client()
        span_call = wc.create_call(
            op=f"openai_agent_{span_type}",
            inputs={"name": span_name},
            parent=parent_call,
            attributes={
                "type": span_type,
                "agent_span_id": span.span_id,
                "agent_trace_id": tid,
                "parent_span_id": getattr(span, "parent_id", None),
            },
            display_name=span_name,
        )
        self._span_calls[span.span_id] = span_call

    def on_span_end(self, span: tracing.Span[Any]) -> None:
        """Called when a span ends."""
        trace_id = span.trace_id
        span_name = _call_name(span)
        span_type = _call_type(span)
        log_data = self._log_data(span)

        # For Response spans, create the call here so we can include input data
        if (
            isinstance(span.span_data, tracing.ResponseSpanData)
            and span.span_id not in self._span_calls
            and trace_id in self._trace_data
            and (parent_call := self._get_parent_call(span))
        ):
            # Create attributes
            attributes = {
                "type": span_type,
                "agent_span_id": span.span_id,
                "agent_trace_id": trace_id,
            }

            # Add parent span ID if present
            if pid := getattr(span, "parent_id", None):
                attributes["parent_span_id"] = pid

            # Create inputs with both name and input data if available
            inputs = {
                "name": span_name,
                "input": log_data["inputs"].get("input"),
            }

            # Create the call now that we have the input data
            wc = require_weave_client()
            span_call = wc.create_call(
                op=f"openai_agent_{span_type}",
                inputs=inputs,
                parent=parent_call,
                attributes=attributes,
                display_name=span_name,
            )
            self._span_calls[span.span_id] = span_call

        # If this span has a call, finish it
        if (span_call := self._span_calls.get(span.span_id)) is None:
            return

        output = {
            "output": log_data["outputs"].get("output"),
            "metrics": log_data["metrics"],
            "metadata": log_data["metadata"],
            "error": log_data["error"],
        }

        # Add error if present
        if span.error:
            output["error"] = span.error
        elif log_data["error"]:
            output["error"] = log_data["error"]

        # Finish the call with the collected data
        wc = require_weave_client()
        wc.finish_call(span_call, output=output)

    def _finish_unfinished_calls(self, status: str) -> None:
        """Helper method for finishing unfinished calls on shutdown or flush."""
        wc = require_weave_client()
        # Finish any unfinished trace calls
        for trace_id, trace_data in self._trace_data.items():
            if trace_id in self._trace_calls:
                trace_call = self._trace_calls[trace_id]

                # Check if call is already finished
                if not getattr(trace_call, "ended_at", None):
                    # Set status based on whether it ended normally
                    actual_status = (
                        "completed" if trace_id in self._ended_traces else status
                    )

                    # Prepare output with the basic trace data
                    output = {
                        "status": actual_status,
                        "metrics": trace_data.get("metrics", {}),
                        "metadata": trace_data.get("metadata", {}),
                    }
                    wc.finish_call(trace_call, output=output)

        # Also finish any unfinished span calls
        for span_call in self._span_calls.values():
            if not getattr(span_call, "ended_at", None):
                wc.finish_call(span_call, output={"status": status})

    def shutdown(self) -> None:
        """Called when the application stops."""
        self._finish_unfinished_calls("interrupted")

    def force_flush(self) -> None:
        """Forces an immediate flush of all queued traces."""
        self._finish_unfinished_calls("force_flushed")


class OpenAIAgentsPatcher(Patcher):
    """
    A patcher for OpenAI Agents that manages the lifecycle of a WeaveTracingProcessor.

    Unlike other patchers that modify function behavior, this patcher installs and
    removes a processor from the OpenAI Agents tracing system.
    """

    def __init__(self, settings: IntegrationSettings) -> None:
        self.settings = settings
        self.patched = False
        self.processor: WeaveTracingProcessor | None = None

    def attempt_patch(self) -> bool:
        """Install a WeaveTracingProcessor in the OpenAI Agents tracing system."""
        if self.patched:
            return True

        try:
            from agents.tracing import add_trace_processor

            self.processor = WeaveTracingProcessor()
            add_trace_processor(self.processor)
            self.patched = True
        except Exception as e:
            self.processor = None
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        # OpenAI Agents doesn't have a way to de-register a processor yet...
        return True


def get_openai_agents_patcher(
    settings: IntegrationSettings | None = None,
) -> OpenAIAgentsPatcher | NoOpPatcher:
    """
    Get a patcher for OpenAI Agents integration.

    Args:
        settings: Optional integration settings to configure the patcher.
            If None, default settings will be used.

    Returns:
        A patcher that can be used to patch and unpatch the OpenAI Agents integration.
    """
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _openai_agents_patcher
    if _openai_agents_patcher is not None:
        return _openai_agents_patcher

    _openai_agents_patcher = OpenAIAgentsPatcher(settings)

    return _openai_agents_patcher
