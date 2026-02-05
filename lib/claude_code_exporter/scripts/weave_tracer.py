"""Weave tracing logic for Claude Code sessions."""

from __future__ import annotations

import sys
from typing import Any

import weave
from weave.trace.weave_client import WeaveClient

from state_manager import SessionState


class WeaveTracer:
    """Handles Weave tracing for Claude Code sessions."""

    def __init__(self, project: str) -> None:
        self.project = project
        self._client: WeaveClient | None = None

    def _get_client(self) -> WeaveClient:
        """Get or initialize the Weave client."""
        if self._client is None:
            self._client = weave.init(self.project)
        return self._client

    def start_session(
        self,
        state: SessionState,
        session_id: str,
        cwd: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Start a root trace for the session.

        Returns:
            Tuple of (call_id, trace_id)
        """
        client = self._get_client()

        inputs = {
            "session_id": session_id,
        }
        if cwd:
            inputs["cwd"] = cwd
        if metadata:
            inputs["metadata"] = metadata

        call = client.create_call(
            op="claude_code_session",
            inputs=inputs,
            display_name=f"Claude Code Session",
        )

        return call.id, call.trace_id

    def finish_session(
        self,
        state: SessionState,
        summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Finish the root session trace."""
        if not state.session_call_id:
            return

        client = self._get_client()

        # Create a minimal call object to finish
        from weave.trace.call import Call

        call = Call(
            _op_name="claude_code_session",
            trace_id=state.session_trace_id or "",
            project_id=client._project_id(),
            parent_id=None,
            inputs={},
            id=state.session_call_id,
        )

        output = summary or {}
        exception = Exception(error) if error else None

        client.finish_call(call, output=output, exception=exception)

    def start_tool_call(
        self,
        state: SessionState,
        tool_name: str,
        tool_use_id: str,
        inputs: dict[str, Any],
    ) -> str:
        """Start a child span for a tool call.

        Returns:
            The call ID for tracking
        """
        client = self._get_client()

        # Get parent from state
        parent_id = state.get_current_parent_id()

        # Create parent call reference if we have one
        parent = None
        if parent_id and state.session_trace_id:
            from weave.trace.call import Call

            parent = Call(
                _op_name="",
                trace_id=state.session_trace_id,
                project_id=client._project_id(),
                parent_id=None,
                inputs={},
                id=parent_id,
            )

        call = client.create_call(
            op=f"tool:{tool_name}",
            inputs=inputs,
            parent=parent,
            display_name=tool_name,
            use_stack=False,  # Don't use context stack, we manage manually
        )

        return call.id

    def finish_tool_call(
        self,
        state: SessionState,
        tool_use_id: str,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """Finish a tool call span."""
        call_id = state.tool_calls.get(tool_use_id)
        if not call_id:
            print(f"Warning: No call found for tool_use_id {tool_use_id}", file=sys.stderr)
            return

        client = self._get_client()

        from weave.trace.call import Call

        call = Call(
            _op_name="",
            trace_id=state.session_trace_id or "",
            project_id=client._project_id(),
            parent_id=state.get_current_parent_id(),
            inputs={},
            id=call_id,
        )

        exception = Exception(error) if error else None
        client.finish_call(call, output=output, exception=exception)

    def start_subagent(
        self,
        state: SessionState,
        subagent_type: str,
        subagent_id: str,
        inputs: dict[str, Any],
    ) -> str:
        """Start a nested span for a subagent.

        Returns:
            The call ID for tracking
        """
        client = self._get_client()

        # Get parent from state
        parent_id = state.get_current_parent_id()

        parent = None
        if parent_id and state.session_trace_id:
            from weave.trace.call import Call

            parent = Call(
                _op_name="",
                trace_id=state.session_trace_id,
                project_id=client._project_id(),
                parent_id=None,
                inputs={},
                id=parent_id,
            )

        call = client.create_call(
            op=f"subagent:{subagent_type}",
            inputs=inputs,
            parent=parent,
            display_name=f"Subagent: {subagent_type}",
            use_stack=False,
        )

        return call.id

    def finish_subagent(
        self,
        state: SessionState,
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """Finish a subagent span (pops from stack)."""
        if not state.subagent_stack:
            print("Warning: No subagent on stack to finish", file=sys.stderr)
            return

        call_id = state.subagent_stack[-1]
        client = self._get_client()

        from weave.trace.call import Call

        # Get the parent (previous item in stack, or session)
        parent_id = None
        if len(state.subagent_stack) > 1:
            parent_id = state.subagent_stack[-2]
        else:
            parent_id = state.session_call_id

        call = Call(
            _op_name="",
            trace_id=state.session_trace_id or "",
            project_id=client._project_id(),
            parent_id=parent_id,
            inputs={},
            id=call_id,
        )

        exception = Exception(error) if error else None
        client.finish_call(call, output=output, exception=exception)

    def start_turn(
        self,
        state: SessionState,
        turn_index: int,
        user_message: str,
    ) -> str:
        """Start a new conversation turn.

        A turn represents one user message and the agent's response,
        including any tool calls in between.

        Returns:
            The call ID for the turn span.
        """
        client = self._get_client()

        # Parent is the session (turns are direct children of session)
        parent = None
        if state.session_call_id and state.session_trace_id:
            from weave.trace.call import Call

            parent = Call(
                _op_name="",
                trace_id=state.session_trace_id,
                project_id=client._project_id(),
                parent_id=None,
                inputs={},
                id=state.session_call_id,
            )

        call = client.create_call(
            op="turn",
            inputs={"user_message": user_message},
            parent=parent,
            display_name=f"Turn #{turn_index}",
            use_stack=False,
        )

        return call.id

    def finish_turn(
        self,
        state: SessionState,
        agent_response: str,
    ) -> None:
        """Finish the current conversation turn with the agent's response."""
        if not state.current_turn_call_id:
            return

        client = self._get_client()

        from weave.trace.call import Call

        call = Call(
            _op_name="turn",
            trace_id=state.session_trace_id or "",
            project_id=client._project_id(),
            parent_id=state.session_call_id,
            inputs={},
            id=state.current_turn_call_id,
        )

        client.finish_call(call, output={"agent_response": agent_response})
