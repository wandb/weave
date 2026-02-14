#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "weave>=0.51.0",
# ]
# ///
"""Main entry point for Claude Code hook events.

This script is invoked by Claude Code hooks and routes events
to the appropriate Weave tracing handlers.

Hook data is passed via stdin as JSON.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# Add the scripts directory to the path for imports
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from state_manager import StateManager, SessionState
from weave_tracer import WeaveTracer


def log_debug(config: Config, message: str) -> None:
    """Print debug message if debug mode is enabled."""
    if config.debug:
        print(f"[weave-exporter] {message}", file=sys.stderr)


def log_info(message: str) -> None:
    """Print info message (always shown)."""
    print(f"[weave-exporter] {message}", file=sys.stderr)


def handle_session_start(data: dict[str, Any], config: Config) -> None:
    """Handle SessionStart event - create root trace."""
    session_id = data.get("session_id", "unknown")
    cwd = data.get("cwd")
    source = data.get("source", "unknown")
    model = data.get("model", "unknown")

    state_manager = StateManager(session_id)
    state = state_manager.load()

    tracer = WeaveTracer(config.project)

    metadata = {
        "source": source,
        "model": model,
    }
    if data.get("agent_type"):
        metadata["agent_type"] = data["agent_type"]

    call_id, trace_id = tracer.start_session(
        state=state,
        session_id=session_id,
        cwd=cwd,
        metadata=metadata,
    )

    state.session_call_id = call_id
    state.session_trace_id = trace_id
    state.project = config.project
    state_manager.save(state)

    log_info(f"Tracing to project: {config.project}")
    log_debug(config, f"Session started: {session_id}, call_id: {call_id}")


def handle_pre_tool_use(data: dict[str, Any], config: Config) -> None:
    """Handle PreToolUse event - create child span for tool."""
    session_id = data.get("session_id", "unknown")
    tool_name = data.get("tool_name", "unknown")
    tool_use_id = data.get("tool_use_id", "unknown")
    tool_input = data.get("tool_input") or {}

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for PreToolUse")
        return

    tracer = WeaveTracer(state.project or config.project)

    call_id = tracer.start_tool_call(
        state=state,
        tool_name=tool_name,
        tool_use_id=tool_use_id,
        inputs=tool_input,
    )

    state.tool_calls[tool_use_id] = call_id
    state_manager.save(state)

    log_debug(config, f"Tool started: {tool_name}")


def handle_post_tool_use(data: dict[str, Any], config: Config) -> None:
    """Handle PostToolUse event - finish child span."""
    session_id = data.get("session_id", "unknown")
    tool_name = data.get("tool_name", "unknown")
    tool_use_id = data.get("tool_use_id", "unknown")
    tool_output = data.get("tool_response")

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for PostToolUse")
        return

    tracer = WeaveTracer(state.project or config.project)

    tracer.finish_tool_call(
        state=state,
        tool_use_id=tool_use_id,
        output=tool_output,
    )

    # Remove from tracking
    state.tool_calls.pop(tool_use_id, None)
    state_manager.save(state)

    log_debug(config, f"Tool finished: {tool_name}")


def handle_subagent_start(data: dict[str, Any], config: Config) -> None:
    """Handle SubagentStart event - create nested span."""
    session_id = data.get("session_id", "unknown")
    subagent_type = data.get("agent_type", "unknown")
    subagent_id = data.get("agent_id", "unknown")
    inputs = {}

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for SubagentStart")
        return

    tracer = WeaveTracer(state.project or config.project)

    call_id = tracer.start_subagent(
        state=state,
        subagent_type=subagent_type,
        subagent_id=subagent_id,
        inputs=inputs,
    )

    # Push to subagent stack
    state.subagent_stack.append(call_id)
    state_manager.save(state)

    log_debug(config, f"Subagent started: {subagent_type}")


def handle_subagent_stop(data: dict[str, Any], config: Config) -> None:
    """Handle SubagentStop event - finish nested span."""
    session_id = data.get("session_id", "unknown")
    subagent_type = data.get("agent_type", "unknown")
    output = None
    error = None

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for SubagentStop")
        return

    tracer = WeaveTracer(state.project or config.project)

    tracer.finish_subagent(
        state=state,
        output=output,
        error=error,
    )

    # Pop from subagent stack
    if state.subagent_stack:
        state.subagent_stack.pop()
    state_manager.save(state)

    log_debug(config, f"Subagent finished: {subagent_type}")


def handle_user_prompt_submit(data: dict[str, Any], config: Config) -> None:
    """Handle UserPromptSubmit event - start a new turn with user message."""
    session_id = data.get("session_id", "unknown")

    log_debug(config, f"UserPromptSubmit data keys: {list(data.keys())}")
    if config.debug:
        log_debug(config, f"UserPromptSubmit data: {json.dumps(data, default=str)[:1000]}")

    user_prompt = data.get("prompt", "")

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for UserPromptSubmit")
        return

    tracer = WeaveTracer(state.project or config.project)

    # Finish any previous turn that wasn't closed
    if state.current_turn_call_id:
        tracer.finish_turn(state=state, agent_response="(turn interrupted)")
        state.current_turn_call_id = None

    # Start a new turn
    state.turn_count = state.turn_count + 1

    call_id = tracer.start_turn(
        state=state,
        turn_index=state.turn_count,
        user_message=user_prompt,
    )

    state.current_turn_call_id = call_id
    state_manager.save(state)
    log_debug(config, f"Turn {state.turn_count} started")


def _extract_usage_from_transcript(transcript_path: str | None, config: Config) -> dict[str, Any]:
    """Extract total token usage from transcript by summing all API calls."""
    if not transcript_path:
        return {}

    try:
        with open(transcript_path) as f:
            content = f.read()

        lines = content.strip().split('\n')

        total_input = 0
        total_output = 0
        total_cache_read = 0
        total_cache_create = 0
        requests = 0
        model = "unknown"

        for line in lines:
            try:
                entry = json.loads(line)
                # Look for usage data in various formats
                usage = entry.get("usage") or entry.get("message", {}).get("usage") or {}
                if usage:
                    total_input += usage.get("input_tokens", 0)
                    total_output += usage.get("output_tokens", 0)
                    total_cache_read += usage.get("cache_read_input_tokens", 0) or usage.get("cacheRead", 0)
                    total_cache_create += usage.get("cache_creation_input_tokens", 0) or usage.get("cacheCreate", 0)
                    requests += 1

                # Try to get model from entries
                if entry.get("model"):
                    model = entry["model"]
            except json.JSONDecodeError:
                continue

        if requests > 0:
            return {
                "model": model,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "cache_read_input_tokens": total_cache_read,
                "cache_creation_input_tokens": total_cache_create,
                "total_tokens": total_input + total_output,
                "requests": requests,
            }
    except Exception as e:
        log_debug(config, f"Error extracting usage from transcript: {e}")

    return {}


def _read_last_assistant_message(transcript_path: str | None, config: Config) -> str:
    """Try to read the last assistant message from the transcript."""
    if not transcript_path:
        log_debug(config, "No transcript path provided")
        return ""

    log_debug(config, f"Reading transcript from: {transcript_path}")

    try:
        with open(transcript_path) as f:
            content = f.read()

        log_debug(config, f"Transcript size: {len(content)} bytes")

        # The transcript is JSONL format
        lines = content.strip().split('\n')
        log_debug(config, f"Transcript has {len(lines)} lines")

        # Find the last assistant message
        for i, line in enumerate(reversed(lines)):
            try:
                entry = json.loads(line)
                entry_type = entry.get("type")
                role = entry.get("role") or entry.get("message", {}).get("role")

                # Log what we're seeing for debugging
                if i < 5:  # Only log last 5 entries
                    log_debug(config, f"Entry {len(lines)-i}: type={entry_type}, role={role}, keys={list(entry.keys())[:5]}")

                # Look for assistant messages - try different structures
                if role == "assistant":
                    # Could be text content or structured
                    msg_content = entry.get("content") or entry.get("message", {}).get("content", "")
                    if isinstance(msg_content, list):
                        # Extract text from content blocks
                        texts = []
                        for block in msg_content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                texts.append(block)
                        result = "\n".join(texts)
                        log_debug(config, f"Found assistant message ({len(result)} chars)")
                        return result
                    elif msg_content:
                        log_debug(config, f"Found assistant message ({len(str(msg_content))} chars)")
                        return str(msg_content)
            except json.JSONDecodeError as e:
                log_debug(config, f"JSON decode error on line {len(lines)-i}: {e}")
                continue

        log_debug(config, "No assistant message found in transcript")
    except FileNotFoundError:
        log_debug(config, f"Transcript file not found: {transcript_path}")
    except Exception as e:
        log_debug(config, f"Error reading transcript: {type(e).__name__}: {e}")

    return ""


def handle_stop(data: dict[str, Any], config: Config) -> None:
    """Handle Stop event - finish the current turn with agent response."""
    session_id = data.get("session_id", "unknown")

    log_debug(config, f"Stop data keys: {list(data.keys())}")
    if config.debug:
        log_debug(config, f"Stop data: {json.dumps(data, default=str)[:1000]}")

    # Stop event doesn't include the response directly; read from transcript
    transcript_path = data.get("transcript_path")
    stop_response = _read_last_assistant_message(transcript_path, config)
    if stop_response:
        log_debug(config, f"Got response from transcript ({len(stop_response)} chars)")

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for Stop")
        return

    tracer = WeaveTracer(state.project or config.project)

    # Finish the current turn
    if state.current_turn_call_id:
        tracer.finish_turn(
            state=state,
            agent_response=stop_response,
        )
        state.current_turn_call_id = None
        state_manager.save(state)
        log_debug(config, f"Turn {state.turn_count} finished")
    else:
        log_debug(config, "Warning: No active turn to finish")


def handle_session_end(data: dict[str, Any], config: Config) -> None:
    """Handle SessionEnd event - finish root trace and cleanup."""
    session_id = data.get("session_id", "unknown")
    reason = data.get("reason", "unknown")

    log_debug(config, f"SessionEnd data keys: {list(data.keys())}")
    if config.debug:
        log_debug(config, f"SessionEnd data: {json.dumps(data, default=str)[:2000]}")

    state_manager = StateManager(session_id)
    state = state_manager.load()

    if not state.session_call_id:
        log_debug(config, "Warning: No session found for SessionEnd")
        state_manager.cleanup()
        return

    tracer = WeaveTracer(state.project or config.project)

    # Finish any remaining open turn
    if state.current_turn_call_id:
        tracer.finish_turn(state=state, agent_response="(session ended)")
        state.current_turn_call_id = None

    # SessionEnd doesn't include usage directly; try extracting from transcript
    usage: dict[str, Any] = {}
    model = "unknown"
    transcript_path = data.get("transcript_path")
    transcript_usage = _extract_usage_from_transcript(transcript_path, config)
    if transcript_usage:
        usage = transcript_usage
        model = transcript_usage.get("model", model)
        log_debug(config, f"Extracted usage from transcript: {usage}")

    # Build summary with usage in Weave LLM format
    summary: dict[str, Any] = {"end_reason": reason}
    if usage:
        # Format: {usage: {model_name: {input_tokens, output_tokens, ...}}}
        usage_entry: dict[str, Any] = {
            "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
            "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "requests": usage.get("requests", 1),
        }
        # Add cache tokens if present
        if usage.get("cache_read_input_tokens"):
            usage_entry["cache_read_input_tokens"] = usage["cache_read_input_tokens"]
        if usage.get("cache_creation_input_tokens"):
            usage_entry["cache_creation_input_tokens"] = usage["cache_creation_input_tokens"]

        summary["usage"] = {model: usage_entry}

    tracer.finish_session(
        state=state,
        summary=summary,
        error=None,
    )

    # Build trace URL
    project = state.project or config.project
    trace_id = state.session_trace_id
    call_id = state.session_call_id
    if "/" in project:
        entity, proj_name = project.split("/", 1)
        trace_url = f"https://wandb.ai/{entity}/{proj_name}/weave/traces/{trace_id}?callId={call_id}"
        log_info(f"View trace: {trace_url}")
    else:
        log_debug(config, f"Session ended: {session_id}")

    # Cleanup state file
    state_manager.cleanup()


EVENT_HANDLERS = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PreToolUse": handle_pre_tool_use,
    "PostToolUse": handle_post_tool_use,
    "SubagentStart": handle_subagent_start,
    "SubagentStop": handle_subagent_stop,
    "Stop": handle_stop,
    "SessionEnd": handle_session_end,
}


def main() -> None:
    """Main entry point - read event from stdin and dispatch."""
    config = None
    try:
        config = Config.from_env()

        if not config.is_valid():
            # Silently exit if not configured
            return

        # Read hook data from stdin
        input_data = sys.stdin.read()
        if not input_data:
            log_debug(config, "Warning: No input data received")
            return

        data = json.loads(input_data)
        event_type = data.get("hook_event_name")

        if not event_type:
            log_debug(config, f"Warning: No hook_event_name in input data: {list(data.keys())}")
            return

        handler = EVENT_HANDLERS.get(event_type)
        if handler:
            handler(data, config)
        else:
            log_debug(config, f"Warning: Unknown event type: {event_type}")

    except json.JSONDecodeError as e:
        print(f"[weave-exporter] Error parsing JSON input: {e}", file=sys.stderr)
    except Exception as e:
        # Log errors but don't fail the hook
        print(f"[weave-exporter] Error: {e}", file=sys.stderr)
        if config and config.debug:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
