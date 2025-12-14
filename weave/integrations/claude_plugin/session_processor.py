"""Factory for creating Weave traces from Claude Code session data.

Provides consistent call creation, summary building, and view attachment
for both live daemon tracing and historic session import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
