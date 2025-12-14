"""Factory for creating Weave traces from Claude Code session data.

Provides consistent call creation, summary building, and view attachment
for both live daemon tracing and historic session import.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from weave.integrations.claude_plugin.utils import (
    generate_session_name,
    get_turn_display_name,
    truncate,
)

if TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient


class SessionProcessor:
    """Factory for creating Weave traces from Claude Code session data.

    Usage:
        processor = SessionProcessor(client, project="entity/project")
        session_call = processor.create_session_call(session_id="abc", first_prompt="Help me...")
        turn_call = processor.create_turn_call(parent=session_call, turn_number=1, ...)
        processor.finish_turn_call(turn_call, turn, session, turn_index)
        processor.finish_session_call(session_call, session, sessions_dir)
    """

    def __init__(
        self,
        client: "WeaveClient",
        project: str,
        source: str = "plugin",
    ) -> None:
        """Initialize SessionProcessor.

        Args:
            client: Initialized Weave client
            project: Project name (e.g., "entity/project") for resume command
            source: "plugin" for live daemon, "import" for historic import
        """
        self.client = client
        self.project = project
        self.source = source

    def create_session_call(
        self,
        session_id: str,
        first_prompt: str,
        cwd: str | None = None,
        git_branch: str | None = None,
        claude_code_version: str | None = None,
    ) -> Any:
        """Create the root session call.

        Generates display name using Ollama summarizer.

        Args:
            session_id: Unique session identifier
            first_prompt: First user prompt (for display name generation)
            cwd: Working directory of the session
            git_branch: Git branch name if available
            claude_code_version: Claude Code version string

        Returns:
            Created Call object (caller stores call.id, call.trace_id, call.ui_url)
        """
        display_name, suggested_branch = generate_session_name(first_prompt)

        return self.client.create_call(
            op="claude_code.session",
            inputs={
                "session_id": session_id,
                "cwd": cwd,
                "git_branch": git_branch,
                "claude_code_version": claude_code_version,
                "suggested_branch_name": suggested_branch or None,
                "first_prompt": truncate(first_prompt, 1000),
            },
            attributes={
                "session_id": session_id,
                "filename": f"{session_id}.jsonl",
                "git_branch": git_branch,
                "source": f"claude-code-{self.source}",
            },
            display_name=display_name,
            use_stack=False,
        )

    def create_turn_call(
        self,
        parent: Any,
        turn_number: int,
        user_message: str,
        *,
        pending_question: str | None = None,
        images: list[Any] | None = None,
        is_compacted: bool = False,
    ) -> Any:
        """Create a turn call as child of session.

        Args:
            parent: Session call (or reconstructed call with trace_id)
            turn_number: 1-based turn number
            user_message: The user's prompt
            pending_question: Question from previous turn (for Q&A context)
            images: Image Content objects from user message
            is_compacted: True if this is a context compaction turn

        Returns:
            Created Call object
        """
        inputs: dict[str, Any] = {
            "user_message": truncate(user_message, 5000),
        }
        if images:
            inputs["images"] = images
        if pending_question:
            inputs["in_response_to"] = pending_question

        display_name = (
            f"Turn {turn_number}: Compacted, resuming..."
            if is_compacted
            else get_turn_display_name(turn_number, user_message)
        )

        attributes: dict[str, Any] = {"turn_number": turn_number}
        if is_compacted:
            attributes["compacted"] = True

        return self.client.create_call(
            op="claude_code.turn",
            inputs=inputs,
            parent=parent,
            attributes=attributes,
            display_name=display_name,
            use_stack=False,
        )
