"""
This module provides integrations between Weave and Strands Agents, allowing Weave to trace
Agent execution, LLM calls, tool usage, and event loop cycles. For more details on Strands Agents, visit:
https://strandsagents.com/latest/user-guide/observability-evaluation/traces/
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

import weave
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings

_strands_patcher: MultiPatcher | None = None


def strands_wrapper(settings: OpSettings) -> Callable:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def safe_serialize_strands_object(obj: Any) -> Any:
    """Safely serialize Strands objects to prevent serialization errors."""
    # Return primitive types directly
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Skip type objects that can't be serialized
    if isinstance(obj, type):
        return f"<class '{obj.__name__}'>"
    
    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        return [safe_serialize_strands_object(item) for item in obj]
    
    # Handle dicts
    if isinstance(obj, dict):
        return {k: safe_serialize_strands_object(v) for k, v in obj.items()}
    
    # For complex objects, try to extract meaningful attributes
    if hasattr(obj, "__dict__"):
        result = {"type": obj.__class__.__name__}
        for attr_name, attr_value in obj.__dict__.items():
            if not attr_name.startswith("_"):
                try:
                    serialized_value = safe_serialize_strands_object(attr_value)
                    result[attr_name] = serialized_value
                except Exception:
                    result[attr_name] = f"<{type(attr_value).__name__}>"
        return result
    
    # Fallback for other objects
    return str(obj)


def strands_postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Postprocess inputs for Strands calls."""
    processed = {}
    
    # Safely serialize all inputs
    for key, value in inputs.items():
        processed[key] = safe_serialize_strands_object(value)
    
    # Extract the main prompt/message if it's the first argument
    if "args" in processed:
        args = processed["args"]
        if isinstance(args, (list, tuple)) and len(args) > 0:
            first_arg = args[0]
            if isinstance(first_arg, str):
                processed["prompt"] = first_arg
    
    return processed


def strands_postprocess_outputs(outputs: Any) -> Any:
    """Postprocess outputs for Strands calls."""
    return safe_serialize_strands_object(outputs)


def default_call_display_name_agent_call(_: Any) -> str:
    """Generate display name for Agent.__call__ operations."""
    return "Agent"


def default_call_display_name_event_loop_cycle(_: Any) -> str:
    """Generate display name for event loop cycle operations."""
    return "Agent Event Loop Cycle"


def default_call_display_name_model_invoke(call: Any) -> str:
    """Generate display name for model invoke operations."""
    # Try to extract model info from args
    if "args" in call.inputs and call.inputs["args"]:
        args = call.inputs["args"]
        if len(args) > 0 and hasattr(args[0], "model_id"):
            model_id = getattr(args[0], "model_id", "unknown")
            return f"Model: {model_id}"
    return "Model Invoke"


def default_call_display_name_tool_call(call: Any) -> str:
    """Generate display name for tool call operations."""
    # Try to extract tool name from args
    if "args" in call.inputs and call.inputs["args"]:
        args = call.inputs["args"]
        if len(args) > 0:
            tool_name = getattr(args[0], "name", "unknown_tool")
            return f"Tool: {tool_name}"
    return "Tool Call"


def get_strands_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _strands_patcher
    if _strands_patcher is not None:
        return _strands_patcher

    base = settings.op_settings

    # Agent.__call__ - main execution method (top-level agent span)
    agent_call_settings = base.model_copy(
        update={
            "name": base.name or "strands.Agent.__call__",
            "call_display_name": base.call_display_name
            or default_call_display_name_agent_call,
            "postprocess_inputs": strands_postprocess_inputs,
            "postprocess_output": strands_postprocess_outputs,
        }
    )

    # Agent._run_loop - internal agent execution
    agent_run_loop_settings = base.model_copy(
        update={
            "name": base.name or "strands.Agent._run_loop",
            "call_display_name": base.call_display_name or "Agent Run Loop",
            "postprocess_inputs": strands_postprocess_inputs,
            "postprocess_output": strands_postprocess_outputs,
        }
    )

    # Event loop cycle - reasoning progression
    event_loop_cycle_settings = base.model_copy(
        update={
            "name": base.name or "strands.event_loop.event_loop_cycle",
            "call_display_name": base.call_display_name 
            or default_call_display_name_event_loop_cycle,
            "postprocess_inputs": strands_postprocess_inputs,
            "postprocess_output": strands_postprocess_outputs,
        }
    )


    # Tool execution
    tool_call_settings = base.model_copy(
        update={
            "name": base.name or "strands.tools.Tool.__call__",
            "call_display_name": base.call_display_name
            or default_call_display_name_tool_call,
            "postprocess_inputs": strands_postprocess_inputs,
            "postprocess_output": strands_postprocess_outputs,
        }
    )

    patchers = []

    # Core Agent patchers
    patchers.extend([
        SymbolPatcher(
            lambda: importlib.import_module("strands"),
            "Agent.__call__",
            strands_wrapper(agent_call_settings),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("strands.agent.agent"),
            "Agent._run_loop",
            strands_wrapper(agent_run_loop_settings),
        ),
    ])

    # Event loop patcher
    try:
        patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("strands.event_loop.event_loop"),
                "event_loop_cycle",
                strands_wrapper(event_loop_cycle_settings),
            )
        )
    except (ImportError, AttributeError):
        pass

    # TODO: Model method patchers temporarily disabled to fix nesting issues
    # The nested calls were likely due to:
    # 1. Multiple inheritance levels being patched 
    # 2. converse() internally calling stream() or other methods
    # 3. Parallel calls being treated as nested calls
    # 
    # For now, focus on Agent-level tracing which provides the most value
    # Model-level tracing can be added back selectively once nesting is resolved

    # Tool execution patchers - check what tools structure looks like
    try:
        # Patch event loop tool execution function
        patchers.append(
            SymbolPatcher(
                lambda: importlib.import_module("strands.event_loop.event_loop"),
                "_handle_tool_execution",
                strands_wrapper(tool_call_settings),
            )
        )
    except (ImportError, AttributeError):
        pass

    _strands_patcher = MultiPatcher(patchers)

    return _strands_patcher