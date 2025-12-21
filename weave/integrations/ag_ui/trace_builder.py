"""Trace Builder for Converting AG-UI Events to Weave Traces

Consumes AG-UI events and produces Weave traces with proper
parent-child relationships and metadata.
"""

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

from weave.integrations.ag_ui.events import (
    AgentEvent,
    FileSnapshotEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingContentEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    UsageRecordedEvent,
)
from weave.integrations.ag_ui.tools import get_tool_registry


class AgentTraceBuilder:
    """Converts AG-UI events into Weave traces.

    Shared across all agent integrations. Handles:
    - Run → Session call hierarchy
    - Step → Turn calls (nested under session)
    - ToolCall → Tool calls (nested under turn)
    - Usage aggregation
    - Parallel tool grouping

    Example:
        builder = AgentTraceBuilder(
            weave_client=weave.init("entity/project"),
            agent_name="Claude Code",
            on_tool_call=lambda event, call: generate_diff_view(event, call),
        )

        for event in parser.parse(session_path):
            builder.handle(event)
    """

    def __init__(
        self,
        weave_client: Any,  # weave.WeaveClient
        agent_name: str,
        on_tool_call: Callable[[ToolCallResultEvent, Any], None] | None = None,
        on_step_finished: Callable[[StepFinishedEvent, Any], None] | None = None,
    ):
        """Initialize the trace builder.

        Args:
            weave_client: Initialized Weave client
            agent_name: Agent name for tool registry lookup
            on_tool_call: Optional hook called after each tool result.
                         Use for integration-specific views (diffs, etc.)
            on_step_finished: Optional hook called after each step finishes.
                            Use for integration-specific behavior (attach diff views, etc.)
        """
        self.client = weave_client
        self.agent_name = agent_name
        self.tool_registry = get_tool_registry(agent_name)
        self.on_tool_call = on_tool_call
        self.on_step_finished = on_step_finished

        # State tracking
        self._run_calls: dict[str, Any] = {}  # run_id → Call
        self._step_calls: dict[str, Any] = {}  # step_id → Call
        self._tool_calls: dict[str, Any] = {}  # tool_call_id → Call
        self._pending_tools: dict[str, ToolCallStartEvent] = {}
        self._tool_args: dict[str, dict[str, Any]] = {}  # tool_call_id → args
        self._current_step_id: str | None = None

        # Session-level tracking for summary
        self._run_metadata: dict[str, dict] = {}  # run_id → metadata
        self._run_step_count: dict[str, int] = {}  # run_id → step count
        self._run_tool_count: dict[str, int] = {}  # run_id → tool count
        self._step_to_run: dict[str, str] = {}  # step_id → run_id

        # Usage tracking: message_id → usage event
        self._message_usage: dict[str, UsageRecordedEvent] = {}

        # Accumulated text content: message_id → content
        self._message_text: dict[str, str] = {}
        self._message_thinking: dict[str, str] = {}

        # Message to step mapping: message_id → step_id
        self._message_to_step: dict[str, str] = {}

        # Tool call tracking for ChatView format: step_id → list of tool call data
        self._step_tool_calls: dict[str, list[dict[str, Any]]] = {}

        # File snapshot tracking per step: step_id → list of Content objects
        self._step_file_snapshots: dict[str, list[Any]] = {}  # Any = Content

        # Q&A context tracking: pending question from previous step
        self._pending_question: str | None = None

    def handle(self, event: AgentEvent) -> None:
        """Process a single event, updating trace state.

        Args:
            event: AG-UI event to process
        """
        match event:
            # Lifecycle
            case RunStartedEvent():
                self._handle_run_started(event)
            case RunFinishedEvent():
                self._handle_run_finished(event)
            case RunErrorEvent():
                self._handle_run_error(event)
            # Steps
            case StepStartedEvent():
                self._handle_step_started(event)
            case StepFinishedEvent():
                self._handle_step_finished(event)
            # Messages
            case TextMessageStartEvent():
                self._handle_message_start(event)
            case TextMessageContentEvent():
                self._handle_text_content(event)
            case TextMessageEndEvent():
                pass  # Message end, content already accumulated
            # Tool calls
            case ToolCallStartEvent():
                self._handle_tool_start(event)
            case ToolCallArgsEvent():
                self._handle_tool_args(event)
            case ToolCallEndEvent():
                pass  # Execution started, wait for result
            case ToolCallResultEvent():
                self._handle_tool_result(event)
            # Tracing extensions
            case UsageRecordedEvent():
                self._handle_usage(event)
            case FileSnapshotEvent():
                self._handle_file_snapshot(event)
            case ThinkingContentEvent():
                self._handle_thinking(event)

    def process_events(self, events: Iterator[AgentEvent]) -> None:
        """Process a stream of events.

        Convenience method for processing multiple events in sequence.

        Args:
            events: Iterator of AG-UI events to process
        """
        for event in events:
            self.handle(event)

    def _handle_run_started(self, event: RunStartedEvent) -> None:
        """Create session call for run start."""
        parent = (
            self._run_calls.get(event.parent_run_id)
            if event.parent_run_id
            else None
        )

        call = self.client.create_call(
            op=f"{self.agent_name.lower().replace(' ', '_')}_session",
            inputs={"prompt": event.input} if event.input else {},
            parent=parent,
        )
        self._run_calls[event.run_id] = call

        # Store metadata for summary generation
        self._run_metadata[event.run_id] = event.metadata.copy()

        # Initialize counters
        self._run_step_count[event.run_id] = 0
        self._run_tool_count[event.run_id] = 0

    def _handle_run_finished(self, event: RunFinishedEvent) -> None:
        """Finish session call with summary."""
        call = self._run_calls.get(event.run_id)
        if call:
            # Build comprehensive summary
            summary: dict[str, Any] = {}

            # Add turn/step count
            step_count = self._run_step_count.get(event.run_id, 0)
            if step_count > 0:
                summary["turn_count"] = step_count

            # Add tool call count
            tool_count = self._run_tool_count.get(event.run_id, 0)
            if tool_count > 0:
                summary["tool_call_count"] = tool_count

            # Add model from metadata if available
            metadata = self._run_metadata.get(event.run_id, {})
            if "model" in metadata:
                summary["model"] = metadata["model"]

            # Add git info if cwd is in metadata
            if "cwd" in metadata:
                git_info = self._get_git_info(metadata["cwd"])
                if git_info:
                    summary["git_info"] = git_info

            # Set summary on call
            if summary:
                call.summary = summary

            # Finish the call
            self.client.finish_call(
                call,
                output={"result": event.result} if event.result else {},
            )

            # Clean up run metadata and counters
            self._run_metadata.pop(event.run_id, None)
            self._run_step_count.pop(event.run_id, None)
            self._run_tool_count.pop(event.run_id, None)

    def _handle_run_error(self, event: RunErrorEvent) -> None:
        """Finish session call with error."""
        call = self._run_calls.get(event.run_id)
        if call:
            self.client.finish_call(
                call,
                exception=Exception(event.message),
            )

    def _handle_step_started(self, event: StepStartedEvent) -> None:
        """Create turn call for step start."""
        parent = self._run_calls.get(event.run_id)
        if not parent:
            return

        # Build inputs
        inputs: dict[str, Any] = {}
        if event.step_name:
            inputs["step_name"] = event.step_name

        # Add Q&A context if we have a pending question from previous step
        if self._pending_question:
            # Build messages in conversation format showing the Q&A flow
            user_message = event.metadata.get("user_message", "")
            if user_message:  # Only add if user provided a message
                inputs["messages"] = [
                    {"role": "assistant", "content": self._pending_question},
                    {"role": "user", "content": user_message},
                ]
                inputs["in_response_to"] = self._pending_question

            # Clear immediately - question consumed by this step
            self._pending_question = None

        call = self.client.create_call(
            op=f"{event.step_type}",
            inputs=inputs if inputs else {},
            parent=parent,
        )
        self._step_calls[event.step_id] = call
        self._current_step_id = event.step_id

        # Track step-to-run mapping and increment step count
        self._step_to_run[event.step_id] = event.run_id
        self._run_step_count[event.run_id] = self._run_step_count.get(event.run_id, 0) + 1

    def _handle_step_finished(self, event: StepFinishedEvent) -> None:
        """Finish turn call with aggregated output and usage."""
        call = self._step_calls.get(event.step_id)
        if not call:
            if self._current_step_id == event.step_id:
                self._current_step_id = None
            return

        # Build output with aggregated content from all messages in this step
        output: dict[str, Any] = {}

        # Aggregate text and thinking from all messages in this step
        assistant_text_parts = []
        thinking_text_parts = []
        usage_by_model: dict[str, dict[str, int]] = {}
        first_model = None

        for message_id, step_id in list(self._message_to_step.items()):
            if step_id != event.step_id:
                continue

            # Collect text content
            text = self._message_text.get(message_id, "")
            if text:
                assistant_text_parts.append(text)

            # Collect thinking content
            thinking = self._message_thinking.get(message_id, "")
            if thinking:
                thinking_text_parts.append(thinking)

            # Collect usage
            usage = self._message_usage.get(message_id)
            if usage and usage.model:
                if first_model is None:
                    first_model = usage.model
                if usage.model not in usage_by_model:
                    usage_by_model[usage.model] = {"input_tokens": 0, "output_tokens": 0}
                usage_by_model[usage.model]["input_tokens"] += usage.input_tokens or 0
                usage_by_model[usage.model]["output_tokens"] += usage.output_tokens or 0

        # Add aggregated content to output
        full_assistant_text = ""
        if assistant_text_parts:
            full_assistant_text = "".join(assistant_text_parts).strip()
            output["content"] = full_assistant_text

        if thinking_text_parts:
            output["reasoning_content"] = "".join(thinking_text_parts).strip()

        # Detect and store pending question for Q&A flow
        # Priority: 1) Explicit pending_question from event, 2) Detect from assistant text
        pending_question = event.pending_question
        if not pending_question and full_assistant_text:
            # Simple question detection: check if text ends with '?' or contains question patterns
            pending_question = self._detect_question(full_assistant_text)

        if pending_question:
            output["pending_question"] = pending_question
            # Store for next step's Q&A context
            self._pending_question = pending_question

        # Add ChatView-compatible message format
        output["role"] = "assistant"
        output["model"] = first_model or "unknown"

        # Add tool_calls in OpenAI format if any tools were called in this step
        tool_calls = self._step_tool_calls.get(event.step_id, [])
        if tool_calls:
            output["tool_calls"] = tool_calls

        # Add file snapshots if any were recorded in this step
        file_snapshots = self._step_file_snapshots.get(event.step_id, [])
        if file_snapshots:
            output["file_snapshots"] = file_snapshots

        # Set usage summary
        if usage_by_model:
            call.summary = {"usage": usage_by_model}

        self.client.finish_call(call, output=output if output else None)

        # Invoke hook for integration-specific behavior (e.g., attach diff views)
        if self.on_step_finished:
            self.on_step_finished(event, call)

        # Clean up state for this step's messages
        for message_id, step_id in list(self._message_to_step.items()):
            if step_id == event.step_id:
                self._message_text.pop(message_id, None)
                self._message_thinking.pop(message_id, None)
                self._message_usage.pop(message_id, None)
                del self._message_to_step[message_id]

        # Clean up tool calls and file snapshots for this step
        self._step_tool_calls.pop(event.step_id, None)
        self._step_file_snapshots.pop(event.step_id, None)

        if self._current_step_id == event.step_id:
            self._current_step_id = None

    def _handle_tool_start(self, event: ToolCallStartEvent) -> None:
        """Record pending tool call."""
        self._pending_tools[event.tool_call_id] = event

    def _handle_tool_args(self, event: ToolCallArgsEvent) -> None:
        """Store tool arguments for use when creating the call."""
        if event.args:
            self._tool_args[event.tool_call_id] = event.args

    def _handle_tool_result(self, event: ToolCallResultEvent) -> None:
        """Create tool call and invoke hook."""
        start_event = self._pending_tools.pop(event.tool_call_id, None)
        if not start_event:
            return

        # Find parent (current step or run)
        parent = None
        if self._current_step_id:
            parent = self._step_calls.get(self._current_step_id)
        if not parent:
            # Fallback to finding any active run
            for run_call in self._run_calls.values():
                parent = run_call
                break

        if not parent:
            return

        # Get tool arguments
        tool_input = self._tool_args.pop(event.tool_call_id, {})

        # Calculate duration if we have timestamps
        duration_ms = None
        started_at = None
        ended_at = None
        if hasattr(event, "timestamp") and hasattr(start_event, "timestamp"):
            duration = (event.timestamp - start_event.timestamp).total_seconds() * 1000
            duration_ms = int(duration)
            started_at = start_event.timestamp
            ended_at = event.timestamp

        # Create tool call directly (inlined from log_tool_call to avoid circular dependency)
        call = self.client.create_call(
            op=start_event.tool_name,
            inputs=tool_input,
            parent=parent,
            started_at=started_at,
        )

        # Finish with result or error
        if event.is_error:
            self.client.finish_call(
                call,
                exception=Exception(event.content or "Tool execution error"),
                ended_at=ended_at,
            )
        else:
            self.client.finish_call(
                call,
                output={"result": event.content},
                ended_at=ended_at,
            )

        # Store summary with duration if available
        if duration_ms is not None:
            call.summary = {"duration_ms": duration_ms}

        self._tool_calls[event.tool_call_id] = call

        # Increment tool count for the run
        if self._current_step_id:
            run_id = self._step_to_run.get(self._current_step_id)
            if run_id:
                self._run_tool_count[run_id] = self._run_tool_count.get(run_id, 0) + 1

        # Track tool call in OpenAI format for ChatView compatibility
        if self._current_step_id:
            if self._current_step_id not in self._step_tool_calls:
                self._step_tool_calls[self._current_step_id] = []

            # Build tool call in OpenAI format with embedded result
            tool_call_data = {
                "id": event.tool_call_id,
                "type": "function",
                "function": {
                    "name": start_event.tool_name,
                    "arguments": json.dumps(tool_input) if tool_input else "{}",
                },
                # Embed the result directly in the tool_call for ChatView
                "response": {
                    "role": "tool",
                    "content": event.content,
                    "tool_call_id": event.tool_call_id,
                },
                "is_error": event.is_error,
            }
            if duration_ms is not None:
                tool_call_data["duration_ms"] = duration_ms

            self._step_tool_calls[self._current_step_id].append(tool_call_data)

        # Invoke hook for integration-specific behavior (e.g., diff view generation)
        if self.on_tool_call:
            self.on_tool_call(event, call)

    def _handle_message_start(self, event: TextMessageStartEvent) -> None:
        """Track message to step mapping."""
        if self._current_step_id:
            self._message_to_step[event.message_id] = self._current_step_id

    def _handle_text_content(self, event: TextMessageContentEvent) -> None:
        """Accumulate text content for a message."""
        # Accumulate content using delta field (streaming)
        if event.delta:
            current = self._message_text.get(event.message_id, "")
            self._message_text[event.message_id] = current + event.delta

    def _handle_usage(self, event: UsageRecordedEvent) -> None:
        """Record token usage for a message."""
        # Store usage by message_id
        self._message_usage[event.message_id] = event

    def _handle_file_snapshot(self, event: FileSnapshotEvent) -> None:
        """Record file snapshot as Content object.

        Converts FileSnapshotEvent to Content object and tracks it per step.
        File snapshots can be used for displaying file diffs or pre-edit backups.
        """
        if not self._current_step_id or not event.content:
            return

        # Import Content here to avoid circular dependency
        from weave.type_wrappers.Content.content import Content

        # Initialize snapshot list for this step if needed
        if self._current_step_id not in self._step_file_snapshots:
            self._step_file_snapshots[self._current_step_id] = []

        # Create Content object from snapshot
        try:
            if isinstance(event.content, bytes):
                content_obj = Content.from_bytes(
                    event.content,
                    mimetype=event.mimetype,
                    metadata={
                        **(event.metadata or {}),
                        "file_path": event.file_path,
                        "is_backup": event.is_backup,
                        "timestamp": event.timestamp.isoformat(),
                    },
                )
            else:
                # String content
                content_obj = Content.from_text(
                    event.content,
                    mimetype=event.mimetype,
                    metadata={
                        **(event.metadata or {}),
                        "file_path": event.file_path,
                        "is_backup": event.is_backup,
                        "timestamp": event.timestamp.isoformat(),
                    },
                )

            self._step_file_snapshots[self._current_step_id].append(content_obj)
        except Exception as e:
            # Log error but don't crash the trace builder
            logging.warning(
                f"Failed to create Content from FileSnapshotEvent: {e}",
                exc_info=True,
            )

    def _handle_thinking(self, event: ThinkingContentEvent) -> None:
        """Accumulate thinking/reasoning content for a message."""
        # Accumulate thinking content
        if event.content:
            current = self._message_thinking.get(event.message_id, "")
            self._message_thinking[event.message_id] = current + event.content

    def _get_git_info(self, cwd: str) -> dict[str, str] | None:
        """Get git repository information for a working directory.

        Uses subprocess with timeout to run git commands safely.
        Returns None on any errors to avoid blocking trace generation.

        Args:
            cwd: Working directory path to check for git repo

        Returns:
            Dict with repo, branch, commit_hash if successful, None otherwise
        """
        import subprocess
        from pathlib import Path

        try:
            cwd_path = Path(cwd)
            if not cwd_path.exists():
                return None

            # Check if it's a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return None

            # Get repo name from remote URL
            repo = None
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Extract repo name from URL
                if url:
                    # Handle both https://github.com/user/repo.git and git@github.com:user/repo.git
                    parts = url.rstrip("/").rstrip(".git").split("/")
                    if len(parts) >= 2:
                        repo = f"{parts[-2]}/{parts[-1]}"
                    elif ":" in url:
                        # Handle git@github.com:user/repo format
                        repo = url.split(":")[-1].rstrip(".git")

            # Get current branch
            branch = None
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()

            # Get commit hash
            commit_hash = None
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                commit_hash = result.stdout.strip()

            # Only return if we got at least some info
            if repo or branch or commit_hash:
                git_info: dict[str, str] = {}
                if repo:
                    git_info["repo"] = repo
                if branch:
                    git_info["branch"] = branch
                if commit_hash:
                    git_info["commit_hash"] = commit_hash
                return git_info

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            # Silently fail on any errors
            pass

        return None

    def _detect_question(self, text: str) -> str | None:
        """Detect if assistant text ends with a question.

        Simple heuristic for Q&A flow detection:
        - Check if text ends with '?'
        - Extract the last sentence/paragraph that contains the question

        Args:
            text: Full assistant response text

        Returns:
            The detected question text, or None if no question detected
        """
        if not text:
            return None

        # Strip and check if ends with question mark
        text = text.strip()
        if not text.endswith("?"):
            return None

        # Extract the last paragraph or sentence containing the question
        # Split by double newlines to get paragraphs
        paragraphs = text.split("\n\n")
        last_para = paragraphs[-1].strip()

        if last_para.endswith("?"):
            # If last paragraph is just the question, return it
            # Otherwise, try to extract the last sentence
            sentences = last_para.split(". ")
            last_sentence = sentences[-1].strip()
            if last_sentence.endswith("?"):
                return last_sentence

            # Fallback: return the whole last paragraph if it contains '?'
            if "?" in last_para:
                return last_para

        return None
