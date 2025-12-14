"""Factory for creating Weave traces from Claude Code session data.

Provides consistent call creation, summary building, and view attachment
for both live daemon tracing and historic session import.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from weave.integrations.claude_plugin.utils import (
    extract_question_from_text,
    generate_session_name,
    get_git_info,
    get_turn_display_name,
    truncate,
)
from weave.trace.view_utils import set_call_view
from weave.type_wrappers.Content.content import Content

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

    def _collect_turn_file_snapshots(
        self,
        turn: Any,
        session_id: str,
    ) -> list[Any]:
        """Collect file backup snapshots for a turn.

        Args:
            turn: Turn object with file_backups
            session_id: Session ID for loading backups

        Returns:
            List of Content objects
        """
        snapshots: list[Any] = []
        for fb in turn.file_backups:
            content = fb.load_content(session_id)
            if content:
                snapshots.append(content)
        return snapshots

    def _collect_session_file_snapshots(
        self,
        session: Any,
        sessions_dir: Path,
    ) -> list[Any]:
        """Collect file snapshots for session output (internal helper).

        Includes:
        - Session JSONL file itself
        - Final state of all changed files (from disk)

        NOTE: This is the internal version without secret scanning.
        For daemon use with secret scanning, use collect_session_file_snapshots_with_scanner.

        Args:
            session: Session object with session_id, cwd, get_all_changed_files()
            sessions_dir: Directory containing session files

        Returns:
            List of Content objects
        """
        snapshots: list[Any] = []

        # Add session JSONL file
        session_file = sessions_dir / f"{session.session_id}.jsonl"
        if session_file.exists():
            try:
                content = Content.from_path(
                    session_file,
                    metadata={
                        "session_id": session.session_id,
                        "filename": session_file.name,
                        "relative_path": "session.jsonl",
                    },
                )
                snapshots.append(content)
            except Exception:
                pass

        # Add final state of changed files
        if session.cwd:
            cwd_path = Path(session.cwd)
            for file_path in session.get_all_changed_files():
                try:
                    abs_path = Path(file_path)
                    if not abs_path.is_absolute():
                        abs_path = cwd_path / file_path

                    if abs_path.exists():
                        try:
                            rel_path = abs_path.relative_to(cwd_path)
                        except ValueError:
                            rel_path = Path(abs_path.name)

                        content = Content.from_path(
                            abs_path,
                            metadata={
                                "original_path": str(file_path),
                                "relative_path": str(rel_path),
                            },
                        )
                        snapshots.append(content)
                except Exception:
                    pass

        return snapshots

    def collect_session_file_snapshots_with_scanner(
        self,
        session: Any,
        sessions_dir: Path,
        secret_scanner: Any | None = None,
    ) -> tuple[list[Any], int]:
        """Collect file snapshots with optional secret scanning (for daemon).

        Includes:
        - Session JSONL file itself
        - Final state of all changed files (from disk)

        Args:
            session: Session object with session_id, cwd, get_all_changed_files()
            sessions_dir: Directory containing session files
            secret_scanner: Optional SecretScanner instance (from get_secret_scanner())

        Returns:
            Tuple of (snapshots list, redacted_count)
        """
        from weave.integrations.claude_plugin.utils import logger

        snapshots: list[Any] = []
        redacted_count = 0

        # Add session JSONL file
        session_file = sessions_dir / f"{session.session_id}.jsonl"
        if session_file.exists():
            try:
                content = Content.from_path(
                    session_file,
                    metadata={
                        "session_id": session.session_id,
                        "filename": session_file.name,
                        "relative_path": "session.jsonl",
                    },
                )
                # Scan for secrets if scanner provided
                if secret_scanner:
                    content, count = secret_scanner.scan_content(content)
                    redacted_count += count
                snapshots.append(content)
                logger.debug(f"Attached session file: {session_file.name}")
            except Exception as e:
                logger.debug(f"Failed to attach session file: {e}")

        # Add final state of changed files
        if session.cwd:
            cwd_path = Path(session.cwd)
            for file_path in session.get_all_changed_files():
                try:
                    abs_path = Path(file_path)
                    if not abs_path.is_absolute():
                        abs_path = cwd_path / file_path

                    if abs_path.exists():
                        try:
                            rel_path = abs_path.relative_to(cwd_path)
                        except ValueError:
                            rel_path = Path(abs_path.name)

                        content = Content.from_path(
                            abs_path,
                            metadata={
                                "original_path": str(file_path),
                                "relative_path": str(rel_path),
                            },
                        )
                        # Scan for secrets if scanner provided
                        if secret_scanner:
                            content, count = secret_scanner.scan_content(content)
                            redacted_count += count
                        snapshots.append(content)
                        logger.debug(f"Attached file snapshot: {rel_path}")
                except Exception as e:
                    logger.debug(f"Failed to attach file {file_path}: {e}")

        return snapshots, redacted_count

    def finish_turn_call(
        self,
        turn_call: Any,
        turn: Any,
        session: Any,
        turn_index: int,
        *,
        interrupted: bool = False,
        extra_file_snapshots: list[Any] | None = None,
    ) -> str | None:
        """Finish turn call with output, summary, and diff view.

        Args:
            turn_call: The call to finish
            turn: Parsed turn data
            session: Full session (for diff context)
            turn_index: 0-based index into session.turns
            interrupted: True if user interrupted this turn
            extra_file_snapshots: Additional snapshots (e.g., from subagents)

        Returns:
            Extracted question from response (for Q&A tracking), or None
        """
        usage = turn.total_usage()
        model = turn.primary_model()

        # Collect assistant text
        assistant_text = ""
        for msg in turn.assistant_messages:
            text = msg.get_text()
            if text:
                assistant_text += text + "\n"

        # Build output (Content objects and actual results only - metadata goes in summary)
        output: dict[str, Any] = {
            "response": truncate(assistant_text.strip()),
        }
        if interrupted:
            output["interrupted"] = True
            output["status"] = "[interrupted]"

        # Collect file snapshots
        file_snapshots = self._collect_turn_file_snapshots(turn, session.session_id)
        if extra_file_snapshots:
            file_snapshots.extend(extra_file_snapshots)
        if file_snapshots:
            output["file_snapshots"] = file_snapshots

        # Build summary
        turn_call.summary = {
            "model": model,
            "tool_call_count": len(turn.all_tool_calls()),
            "duration_ms": turn.duration_ms(),
        }
        if model and usage:
            turn_call.summary["usage"] = {model: usage.to_weave_usage()}

        # Attach diff view
        self._attach_turn_diff_view(
            turn_call,
            turn,
            session,
            turn_index,
            user_prompt=turn.user_message.content if turn.user_message else None,
        )

        # Finish
        self.client.finish_call(turn_call, output=output)

        # Extract and return pending question for next turn
        if not interrupted:
            return extract_question_from_text(assistant_text)
        return None

    def _attach_turn_diff_view(
        self,
        turn_call: Any,
        turn: Any,
        session: Any,
        turn_index: int,
        user_prompt: str | None = None,
    ) -> None:
        """Generate and attach turn-level diff HTML view."""
        from weave.integrations.claude_plugin.diff_view import (
            generate_turn_diff_html,
            generate_diff_html_from_edit_data_for_turn,
        )

        # Try file-history-based diff first
        diff_html = generate_turn_diff_html(
            turn=turn,
            turn_index=turn_index,
            all_turns=session.turns,
            session_id=session.session_id,
            turn_number=turn_index + 1,
            tool_count=len(turn.all_tool_calls()),
            model=turn.primary_model(),
            historic_mode=(self.source == "import"),
            cwd=session.cwd,
            user_prompt=user_prompt,
        )

        # Fallback to Edit tool data
        if not diff_html and turn.raw_messages:
            diff_html = generate_diff_html_from_edit_data_for_turn(
                turn=turn,
                turn_number=turn_index + 1,
                user_prompt=user_prompt,
            )

        if diff_html:
            set_call_view(
                call=turn_call,
                client=self.client,
                name="file_changes",
                content=diff_html,
                extension="html",
                mimetype="text/html",
            )

    def finish_session_call(
        self,
        session_call: Any,
        session: Any,
        sessions_dir: Path,
        *,
        end_reason: str | None = None,
        extra_summary: dict[str, Any] | None = None,
    ) -> None:
        """Finish session call with summary, file snapshots, and diff view.

        Args:
            session_call: The call to finish (may be reconstructed)
            session: Parsed session data
            sessions_dir: Directory containing session files (for subagent lookup)
            end_reason: Optional reason (e.g., "user_exit", "timeout")
            extra_summary: Additional summary fields (compaction_count, redacted_secrets)
        """
        # Build summary
        usage = session.total_usage()
        model = session.primary_model()

        summary: dict[str, Any] = {
            "turn_count": len(session.turns),
            "tool_call_count": session.total_tool_calls(),
            "tool_call_breakdown": session.tool_call_counts(),
            "duration_ms": session.duration_ms(),
            "model": model,
        }
        if model and usage:
            summary["usage"] = {model: usage.to_weave_usage()}
        if end_reason:
            summary["end_reason"] = end_reason

        # Add git info if available (for teleport feature)
        if session.cwd:
            git_info = get_git_info(session.cwd)
            if git_info:
                summary["git"] = git_info

        if extra_summary:
            summary.update(extra_summary)

        # Collect file snapshots
        output: dict[str, Any] = {}
        file_snapshots = self._collect_session_file_snapshots(session, sessions_dir)
        if file_snapshots:
            output["file_snapshots"] = file_snapshots

        # Set summary before attaching view
        session_call.summary = summary

        # Attach diff view
        self._attach_session_diff_view(session_call, session, sessions_dir)

        # Finish
        self.client.finish_call(session_call, output=output)

    def _attach_session_diff_view(
        self,
        session_call: Any,
        session: Any,
        sessions_dir: Path,
    ) -> None:
        """Generate and attach session-level diff HTML view."""
        from weave.integrations.claude_plugin.diff_view import (
            generate_session_diff_html,
        )

        # Try file-history-based diff
        diff_html = generate_session_diff_html(
            session,
            cwd=session.cwd,
            sessions_dir=sessions_dir,
            project=self.project,
        )

        # TODO: Add fallback to Edit data in future enhancement

        if diff_html:
            set_call_view(
                call=session_call,
                client=self.client,
                name="file_changes",
                content=diff_html,
                extension="html",
                mimetype="text/html",
            )
