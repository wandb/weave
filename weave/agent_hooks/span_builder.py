"""OTel span lifecycle manager for agent session tracing.

Translates normalized ``AgentHookEvent`` objects into OTel spans that follow
the GenAI semantic conventions, so Cursor/Claude Code/Codex sessions appear
correctly in the Weave traces, agents, and conversations views.

Span hierarchy produced per turn (each turn is a separate trace)::

    invoke_agent cursor-agent          (user_prompt → stop)
    ├── execute_tool Read              (tool_use_start → tool_use_end)
    ├── execute_tool bash              (shell_exec — instant)
    ├── invoke_agent subagent-type     (subagent_start → subagent_stop)
    └── ...

All turns within a conversation share ``gen_ai.conversation.id`` so they
can be stitched together in the Conversations view.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Span

from weave.agent_hooks.events import AgentHookEvent

logger = logging.getLogger(__name__)

_TOOL_OUTPUT_TRUNCATE = 4096
# Max bytes to store from a transcript file on a span attribute.
_TRANSCRIPT_TRUNCATE = 32_768


class _TurnState:
    """Open-span state for one turn (generation_id) within a conversation."""

    def __init__(self) -> None:
        self.agent_span: Span | None = None
        self.agent_ctx: Any = None
        self.prompt: str = ""
        self.response: str = ""
        self.transcript_path: str = ""
        self.attachments: list[dict] = []
        # tool_use_id → (Span, ctx)
        self.tool_spans: dict[str, tuple[Span, Any]] = {}
        # subagent_id → Span
        self.subagent_spans: dict[str, Span] = {}


class _ConvState:
    """State for one conversation (conversation_id), holding per-turn state."""

    def __init__(self) -> None:
        self.model: str = ""
        self.source: str = ""
        self.workspace: str = ""
        self.is_background_agent: bool = False
        self.composer_mode: str = ""
        self.current_turn: _TurnState | None = None


class SpanBuilder:
    """Manages the OTel span lifecycle for all active agent conversations.

    Each turn (identified by ``generation_id``) gets its own root
    ``invoke_agent`` span.  Turns within a conversation share
    ``gen_ai.conversation.id``.

    Args:
        provider: Configured OTel ``TracerProvider``.  Must have exporters
            set up before the first event is processed.

    Examples:
        >>> from opentelemetry.sdk.trace import TracerProvider
        >>> builder = SpanBuilder(TracerProvider())
        >>> # events come in via builder.handle(event)
    """

    def __init__(self, provider: TracerProvider) -> None:
        self._provider = provider
        self._tracer = provider.get_tracer("weave.agent_hooks")
        self._lock = threading.Lock()
        self._convs: dict[str, _ConvState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, event: AgentHookEvent) -> None:
        """Dispatch a normalized event to the appropriate handler."""
        try:
            self._dispatch(event)
        except Exception:
            logger.exception("span_builder error on %s", event.event_kind)

    def flush(self) -> None:
        """Force-flush all pending spans to the exporter."""
        self._provider.force_flush()

    def shutdown(self) -> None:
        """Flush and shut down the provider."""
        self._provider.force_flush()
        self._provider.shutdown()

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, ev: AgentHookEvent) -> None:
        logger.info(
            "event %-20s conv=%.16s gen=%.8s tool=%s",
            ev.event_kind,
            ev.conversation_id or "-",
            ev.generation_id or "-",
            ev.tool_name or "-",
        )
        kind = ev.event_kind
        if kind == "session_start":
            self._on_session_start(ev)
        elif kind == "session_end":
            self._on_session_end(ev)
        elif kind == "user_prompt":
            self._on_user_prompt(ev)
        elif kind == "agent_response":
            self._on_agent_response(ev)
        elif kind == "agent_thought":
            self._on_agent_thought(ev)
        elif kind == "tool_use_start":
            self._on_tool_use_start(ev)
        elif kind in {"tool_use_end", "tool_use_failed"}:
            self._on_tool_use_end(ev)
        elif kind == "shell_exec":
            self._on_shell_exec(ev)
        elif kind == "mcp_call":
            self._on_mcp_call(ev)
        elif kind == "file_edit":
            self._on_file_edit(ev)
        elif kind == "subagent_start":
            self._on_subagent_start(ev)
        elif kind == "subagent_stop":
            self._on_subagent_stop(ev)
        elif kind == "context_compacted":
            self._on_context_compacted(ev)
        elif kind == "stop":
            self._on_stop(ev)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _get_conv(self, conv_id: str) -> _ConvState:
        with self._lock:
            if conv_id not in self._convs:
                self._convs[conv_id] = _ConvState()
            return self._convs[conv_id]

    def _get_turn(self, ev: AgentHookEvent) -> tuple[_ConvState, _TurnState | None]:
        """Return (conv, turn) where turn may be ``None`` if no turn is open.

        Only ``_on_user_prompt`` opens turns.  All other handlers should call
        this and skip gracefully when turn is ``None`` — those events arrived
        outside a user-initiated turn boundary (e.g. after a daemon restart
        or between ``stop`` and the next ``beforeSubmitPrompt``).
        """
        conv = self._get_conv(ev.conversation_id)
        if conv.source == "" and ev.source:
            conv.source = ev.source
        if conv.model == "" and ev.model:
            conv.model = ev.model
        if conv.workspace == "" and ev.workspace_roots:
            conv.workspace = ev.workspace_roots[0]
        return conv, conv.current_turn

    def _open_turn(self, conv: _ConvState, ev: AgentHookEvent) -> _TurnState:
        """Open a new turn: create root invoke_agent span."""
        agent_label = f"{conv.source or ev.source or 'ide'}-agent"
        workspace = conv.workspace or (ev.workspace_roots[0] if ev.workspace_roots else "")

        turn = _TurnState()
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_label,
            "gen_ai.system": conv.source or ev.source or "ide",
            "gen_ai.request.model": ev.model or conv.model,
            "gen_ai.conversation.id": ev.conversation_id,
            "weave.agent_hooks.source": conv.source or ev.source or "ide",
            "weave.agent_hooks.workspace": workspace,
        }
        if conv.composer_mode:
            attrs["weave.session.composer_mode"] = conv.composer_mode
        if conv.is_background_agent:
            attrs["weave.session.is_background_agent"] = True

        span, ctx = self._start_span(f"invoke_agent {agent_label}", None, attrs)
        turn.agent_span = span
        turn.agent_ctx = ctx
        conv.current_turn = turn
        return turn

    def _close_turn(self, conv: _ConvState, stop_status: str = "", loop_count: int = 0) -> None:
        """Close the current turn: attach prompt/response to root span, end all spans."""
        turn = conv.current_turn
        if turn is None:
            return

        # Attach user prompt (and any file attachments) to the root invoke_agent span
        if turn.prompt or turn.attachments:
            input_msgs = []
            if turn.attachments:
                # Represent attached files/rules as context in the message array
                attachment_paths = [
                    a.get("file_path", "") for a in turn.attachments if a.get("file_path")
                ]
                if attachment_paths:
                    turn.agent_span.set_attribute(  # type: ignore[union-attr]
                        "weave.prompt.attachments", json.dumps(attachment_paths)
                    )
            if turn.prompt:
                input_msgs.append({"role": "user", "content": turn.prompt})
            if input_msgs:
                turn.agent_span.set_attribute(  # type: ignore[union-attr]
                    "gen_ai.input.messages", json.dumps(input_msgs)
                )

        # Record turn completion metadata
        if stop_status:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.stop_status", stop_status
            )
        if loop_count:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.loop_count", loop_count
            )

        # Store the transcript path so viewers can open the raw file
        if turn.transcript_path:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.transcript_path", turn.transcript_path
            )
            # Opportunistically read and attach the transcript content
            content = _read_transcript(turn.transcript_path)
            if content:
                turn.agent_span.set_attribute(  # type: ignore[union-attr]
                    "weave.turn.transcript", content[:_TRANSCRIPT_TRUNCATE]
                )

        # Set OTel span status based on stop outcome
        if stop_status == "error":
            from opentelemetry.trace import StatusCode
            turn.agent_span.set_status(StatusCode.ERROR, "agent error")  # type: ignore[union-attr]
        elif stop_status == "aborted":
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.aborted", True
            )

        # Close any dangling child spans
        for tool_span, _ in turn.tool_spans.values():
            tool_span.end()
        turn.tool_spans.clear()

        for sub_span in turn.subagent_spans.values():
            sub_span.end()
        turn.subagent_spans.clear()

        if turn.agent_span:
            turn.agent_span.end()

        conv.current_turn = None

    def _start_span(
        self,
        name: str,
        parent_ctx: Any,
        attributes: dict[str, Any],
    ) -> tuple[Span, Any]:
        """Start a span with *parent_ctx* and return (span, ctx_with_span)."""
        from opentelemetry import trace

        span = self._tracer.start_span(name, context=parent_ctx, attributes=attributes)
        ctx = trace.set_span_in_context(span)
        return span, ctx

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_session_start(self, ev: AgentHookEvent) -> None:
        conv = self._get_conv(ev.conversation_id)
        conv.source = ev.source
        conv.model = ev.model
        conv.workspace = ev.workspace_roots[0] if ev.workspace_roots else ""
        conv.is_background_agent = ev.is_background_agent
        conv.composer_mode = ev.composer_mode

    def _on_session_end(self, ev: AgentHookEvent) -> None:
        conv = self._get_conv(ev.conversation_id)
        self._close_turn(conv)
        with self._lock:
            self._convs.pop(ev.conversation_id, None)
        self._provider.force_flush()

    def _on_stop(self, ev: AgentHookEvent) -> None:
        """Agent loop ended for one turn — close turn with status, export spans."""
        conv = self._get_conv(ev.conversation_id)
        self._close_turn(conv, stop_status=ev.stop_status, loop_count=ev.loop_count)

    def _on_user_prompt(self, ev: AgentHookEvent) -> None:
        conv = self._get_conv(ev.conversation_id)
        # Close any previous turn that wasn't closed by stop
        self._close_turn(conv)
        # Open a new turn
        turn = self._open_turn(conv, ev)
        turn.prompt = ev.prompt_text
        turn.attachments = ev.attachments
        if ev.transcript_path:
            turn.transcript_path = ev.transcript_path

        # Emit an instant child span carrying the user prompt so it is
        # exported immediately, even if the daemon is killed before stop fires.
        # The chat view's find_user_prompt() picks this up as a fallback when
        # the root invoke_agent span is missing.
        if ev.prompt_text:
            attrs: dict[str, Any] = {
                "gen_ai.operation.name": "chat",
                "gen_ai.conversation.id": ev.conversation_id,
                "gen_ai.input.messages": json.dumps(
                    [{"role": "user", "content": ev.prompt_text}]
                ),
            }
            if ev.attachments:
                attachment_paths = [
                    a.get("file_path", "") for a in ev.attachments if a.get("file_path")
                ]
                if attachment_paths:
                    attrs["weave.prompt.attachments"] = json.dumps(attachment_paths)
            user_span, _ = self._start_span("chat", turn.agent_ctx, attrs)
            user_span.end()

    def _on_agent_response(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        turn.response = ev.response_text
        if ev.response_text:
            span, _ = self._start_span(
                "chat",
                turn.agent_ctx,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": ev.model or "",
                    "gen_ai.conversation.id": ev.conversation_id,
                    "gen_ai.output.messages": json.dumps(
                        [{"role": "assistant", "content": ev.response_text}]
                    ),
                },
            )
            span.end()

    def _on_agent_thought(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        if ev.thought_text:
            span, _ = self._start_span(
                "chat",
                turn.agent_ctx,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": ev.model or "",
                    "gen_ai.conversation.id": ev.conversation_id,
                    "gen_ai.output.messages": json.dumps(
                        [{"role": "assistant", "content": ev.thought_text}]
                    ),
                },
            )
            span.end()

    def _on_tool_use_start(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        tool_args = json.dumps(ev.tool_input) if ev.tool_input else ""
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": ev.tool_name,
            "gen_ai.tool.call.arguments": tool_args,
            "gen_ai.conversation.id": ev.conversation_id,
        }
        # Capture the agent's stated reasoning for invoking this tool — this is
        # model output that shows *why* the tool is being called.
        if ev.agent_message:
            attrs["gen_ai.agent.message"] = ev.agent_message
        if ev.cwd:
            attrs["weave.tool.cwd"] = ev.cwd
        span, ctx = self._start_span(f"execute_tool {ev.tool_name}", turn.agent_ctx, attrs)
        key = ev.tool_use_id or ev.tool_name
        turn.tool_spans[key] = (span, ctx)

    def _on_tool_use_end(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        key = ev.tool_use_id or ev.tool_name
        entry = turn.tool_spans.pop(key, None)
        if entry is None:
            self._emit_instant_tool(ev)
            return

        span, _ = entry
        if ev.event_kind == "tool_use_end" and ev.tool_output:
            span.set_attribute(
                "gen_ai.tool.call.result", ev.tool_output[:_TOOL_OUTPUT_TRUNCATE]
            )
        if ev.event_kind == "tool_use_failed":
            if ev.tool_error:
                span.set_attribute("gen_ai.tool.call.result", ev.tool_error)
            if ev.failure_type:
                span.set_attribute("weave.tool.failure_type", ev.failure_type)
            if ev.is_interrupt:
                span.set_attribute("weave.tool.is_interrupt", True)
            from opentelemetry.trace import StatusCode
            span.set_status(StatusCode.ERROR, ev.tool_error or ev.failure_type or "tool failed")
        span.end()

    def _emit_instant_tool(self, ev: AgentHookEvent) -> None:
        """Emit a single-point span for a tool call with no preToolUse."""
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        tool_args = json.dumps(ev.tool_input) if ev.tool_input else ""
        span, _ = self._start_span(
            f"execute_tool {ev.tool_name}",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": ev.tool_name,
                "gen_ai.tool.call.arguments": tool_args,
                "gen_ai.tool.call.result": ev.tool_output[:_TOOL_OUTPUT_TRUNCATE],
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        span.end()

    def _on_shell_exec(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        # Skip when a Shell tool span is already open (preToolUse covers it)
        if turn.tool_spans:
            return
        span, _ = self._start_span(
            "execute_tool bash",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "bash",
                "gen_ai.tool.call.arguments": json.dumps({"command": ev.shell_command}),
                "gen_ai.tool.call.result": ev.shell_output[:_TOOL_OUTPUT_TRUNCATE],
                "weave.shell.exit_code": ev.shell_exit_code,
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        if ev.shell_exit_code != 0:
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.ERROR, f"exit {ev.shell_exit_code}")
        span.end()

    def _on_mcp_call(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        tool_label = f"{ev.mcp_server}/{ev.tool_name}" if ev.mcp_server else ev.tool_name
        span, _ = self._start_span(
            f"execute_tool {tool_label}",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_label,
                "gen_ai.tool.call.arguments": json.dumps(ev.tool_input) if ev.tool_input else "",
                "gen_ai.tool.call.result": ev.tool_output[:_TOOL_OUTPUT_TRUNCATE],
                "weave.mcp.server": ev.mcp_server,
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        span.end()

    def _on_file_edit(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        # Skip when a Write tool span is already open (preToolUse covers it)
        if turn.tool_spans:
            return
        span, _ = self._start_span(
            "execute_tool edit_file",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "edit_file",
                "gen_ai.tool.call.arguments": json.dumps({"path": ev.file_path}),
                "weave.file.path": ev.file_path,
                "weave.file.edit_count": len(ev.file_edits),
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        span.end()

    def _on_subagent_start(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        agent_label = ev.subagent_type or "subagent"
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_label,
            "gen_ai.request.model": ev.subagent_model or ev.model or "",
            "gen_ai.system_instructions": ev.subagent_task,
            "gen_ai.conversation.id": ev.conversation_id,
            "weave.subagent.id": ev.subagent_id,
            "weave.subagent.type": ev.subagent_type,
        }
        if ev.tool_call_id:
            attrs["weave.subagent.tool_call_id"] = ev.tool_call_id
        if ev.is_parallel_worker:
            attrs["weave.subagent.is_parallel_worker"] = True
        if ev.git_branch:
            attrs["weave.subagent.git_branch"] = ev.git_branch
        span, _ = self._start_span(f"invoke_agent {agent_label}", turn.agent_ctx, attrs)
        turn.subagent_spans[ev.subagent_id] = span

    def _on_subagent_stop(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        span = turn.subagent_spans.pop(ev.subagent_id, None)
        if span is None:
            return
        if ev.subagent_summary:
            span.set_attribute("gen_ai.output.messages", json.dumps(
                [{"role": "assistant", "content": ev.subagent_summary}]
            ))
        span.set_attribute("weave.subagent.status", ev.subagent_status)
        span.set_attribute("weave.subagent.tool_call_count", ev.subagent_tool_call_count)
        if ev.subagent_message_count:
            span.set_attribute("weave.subagent.message_count", ev.subagent_message_count)
        if ev.subagent_loop_count:
            span.set_attribute("weave.subagent.loop_count", ev.subagent_loop_count)
        if ev.subagent_modified_files:
            span.set_attribute(
                "weave.subagent.modified_files",
                json.dumps(ev.subagent_modified_files),
            )
        if ev.agent_transcript_path:
            span.set_attribute("weave.subagent.transcript_path", ev.agent_transcript_path)
        if ev.subagent_status == "error":
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.ERROR, "subagent failed")
        span.end()

    def _on_context_compacted(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        if turn.agent_span:
            event_attrs: dict[str, Any] = {
                "context_tokens": ev.context_tokens,
                "context_window_size": ev.context_window,
                "usage_pct": round(ev.context_tokens / max(ev.context_window, 1) * 100),
            }
            if ev.compact_trigger:
                event_attrs["trigger"] = ev.compact_trigger
            if ev.context_usage_percent:
                event_attrs["context_usage_percent"] = ev.context_usage_percent
            if ev.message_count:
                event_attrs["message_count"] = ev.message_count
            if ev.messages_to_compact:
                event_attrs["messages_to_compact"] = ev.messages_to_compact
            # Always record is_first_compaction (False is informative too)
            event_attrs["is_first_compaction"] = ev.is_first_compaction
            turn.agent_span.add_event("context_compacted", event_attrs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_transcript(path: str) -> str | None:
    """Read a Cursor transcript file, returning its text content or None.

    Args:
        path: Absolute path to the transcript file.

    Returns:
        File contents as a string, or ``None`` if the file cannot be read.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None
