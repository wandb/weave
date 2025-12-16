"""Factory for creating Weave traces from Claude Code session data.

Provides consistent call creation, summary building, and view attachment
for both live daemon tracing and historic session import.
"""

from __future__ import annotations

import json
import socket
from datetime import datetime
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


def get_hostname() -> str:
    """Get the hostname of the current machine."""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"

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

    @staticmethod
    def _get_mimetype_for_extension(ext: str) -> str:
        """Get MIME type for a file extension."""
        EXT_TO_MIMETYPE = {
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".ts": "text/typescript",
            ".tsx": "text/typescript",
            ".jsx": "text/javascript",
            ".json": "application/json",
            ".yaml": "text/yaml",
            ".yml": "text/yaml",
            ".md": "text/plain",
            ".html": "text/html",
            ".css": "text/css",
            ".sh": "text/x-shellscript",
            ".toml": "text/toml",
            ".txt": "text/plain",
        }
        return EXT_TO_MIMETYPE.get(ext, "text/plain")

    def create_session_call(
        self,
        session_id: str,
        first_prompt: str,
        cwd: str | None = None,
        git_branch: str | None = None,
        claude_code_version: str | None = None,
        display_name: str | None = None,
        continuation_of: str | None = None,
        started_at: datetime | None = None,
    ) -> tuple[Any, str]:
        """Create the root session call.

        Generates display name using Ollama summarizer unless provided.

        Args:
            session_id: Unique session identifier
            first_prompt: First user prompt (for display name generation)
            cwd: Working directory of the session
            git_branch: Git branch name if available
            claude_code_version: Claude Code version string
            display_name: Optional display name (overrides generated name)
            continuation_of: If this is a continuation, the previous call_id
            started_at: Optional timestamp override for retroactive logging

        Returns:
            Tuple of (Created Call object, display_name used)
        """
        if display_name is None:
            display_name, _ = generate_session_name(first_prompt)

        # Build attributes
        attributes: dict[str, Any] = {
            "session_id": session_id,
            "filename": f"{session_id}.jsonl",
            "git_branch": git_branch,
            "source": f"claude-code-{self.source}",
            "hostname": get_hostname(),
        }

        # Add continuation metadata if this is a continuation
        if continuation_of:
            attributes["continuation_of"] = continuation_of

        call = self.client.create_call(
            op="claude_code.session",
            inputs={
                "session_id": session_id,
                "cwd": cwd,
                "git_branch": git_branch,
                "claude_code_version": claude_code_version,
                "first_prompt": truncate(first_prompt, 1000),
            },
            attributes=attributes,
            display_name=display_name,
            use_stack=False,
            started_at=started_at,
        )

        return call, display_name

    def create_turn_call(
        self,
        parent: Any,
        turn_number: int,
        user_message: str,
        *,
        pending_question: str | None = None,
        images: list[Any] | None = None,
        is_compacted: bool = False,
        started_at: datetime | None = None,
    ) -> Any:
        """Create a turn call as child of session.

        Args:
            parent: Session call (or reconstructed call with trace_id)
            turn_number: 1-based turn number
            user_message: The user's prompt
            pending_question: Question from previous turn (for Q&A context)
            images: Image Content objects from user message
            is_compacted: True if this is a context compaction turn
            started_at: Optional timestamp override for retroactive logging

        Returns:
            Created Call object
        """
        # Build Anthropic-format message content for chat view detection
        user_content: str | list[dict[str, Any]] = truncate(user_message, 5000)
        if images:
            # Include images in Anthropic format alongside text
            content_parts: list[dict[str, Any]] = [
                {"type": "text", "text": truncate(user_message, 5000)}
            ]
            for img in images:
                # Content objects have to_anthropic_format() or we use dict format
                if hasattr(img, "to_dict"):
                    content_parts.append({"type": "image", "source": img.to_dict()})
                else:
                    content_parts.append({"type": "image", "source": img})
            user_content = content_parts

        # Build messages array for ChatView
        # For Q&A flow, prepend the question as an assistant message
        messages: list[dict[str, Any]] = []
        if pending_question:
            messages.append({"role": "assistant", "content": pending_question})
        messages.append({"role": "user", "content": user_content})

        inputs: dict[str, Any] = {
            # Anthropic-format messages for chat view detection
            "messages": messages,
        }
        if pending_question:
            inputs["in_response_to"] = pending_question

        display_name = (
            f"Turn {turn_number}: Compacted, resuming..."
            if is_compacted
            else get_turn_display_name(turn_number, user_message, pending_question)
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
            started_at=started_at,
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

        For imports (historic sessions):
        - Session JSONL file itself
        - File backups with actual Claude backup data (backup_filename set)

        For daemon (live sessions):
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

        # For imports, reconstruct file snapshots from Edit data
        # This captures changes from main session AND all subagents
        # Don't load from disk since files may have changed since the session
        if self.source == "import":
            from weave.integrations.claude_plugin.views.diff_utils import (
                collect_all_file_changes_from_session,
            )

            file_changes = collect_all_file_changes_from_session(session, sessions_dir)
            cwd_path = Path(session.cwd) if session.cwd else None

            for file_path, change_info in file_changes.items():
                # Use the "after" state (final file content after all edits)
                after_content = change_info.get("after")
                if not after_content:
                    continue

                try:
                    # Determine relative path for metadata
                    abs_path = Path(file_path)
                    if cwd_path and abs_path.is_absolute():
                        try:
                            rel_path = abs_path.relative_to(cwd_path)
                        except ValueError:
                            rel_path = Path(abs_path.name)
                    else:
                        rel_path = abs_path

                    # Determine extension and mimetype
                    ext = abs_path.suffix.lower()
                    mimetype = self._get_mimetype_for_extension(ext)

                    content = Content.from_bytes(
                        after_content.encode("utf-8"),
                        mimetype=mimetype,
                        extension=ext or ".txt",
                        metadata={
                            "original_path": str(file_path),
                            "relative_path": str(rel_path),
                            "source": "edit_data",
                        },
                    )
                    snapshots.append(content)
                except Exception:
                    pass
        else:
            # For daemon (live mode), load final state from disk
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

    @staticmethod
    def build_turn_output(
        turn: Any,
        *,
        interrupted: bool = False,
    ) -> tuple[dict[str, Any], str, str]:
        """Build turn output in Message format for ChatView.

        Creates output compatible with Weave's ChatView Message format:
        - role: "assistant"
        - content: Main text response (string)
        - model: Model name
        - reasoning_content: Thinking content (for collapsible UI)
        - tool_calls: Tool calls in OpenAI format with embedded results

        Args:
            turn: Parsed turn data with assistant_messages and tool calls
            interrupted: True if user interrupted this turn

        Returns:
            Tuple of (output_dict, assistant_text, thinking_text)
        """
        model = turn.primary_model()

        # Collect assistant text and thinking content from all assistant messages
        assistant_text = ""
        thinking_text = ""
        for msg in turn.assistant_messages:
            text = msg.get_text()
            if text:
                assistant_text += text + "\n"
            if msg.thinking_content:
                thinking_text += msg.thinking_content + "\n"

        # Build output in Message format for ChatView
        # Note: We use Message format (not Anthropic's native format with type: "message")
        # because the ChatView Anthropic normalizer requires all content blocks to be text-only.
        # By omitting "type", the output passes through as a raw Message object which gives us:
        # - reasoning_content: Collapsible "Thinking" UI
        # - tool_calls: Expandable tool calls with embedded results
        # Note: Don't truncate turn content - it's the primary output and truncation
        # breaks Q&A detection when questions appear at the end of long responses
        output: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_text.strip(),
            "model": model or "claude-sonnet-4-20250514",
        }

        # Add thinking/reasoning content for collapsible UI
        # Note: Don't truncate reasoning either - it's important context
        if thinking_text.strip():
            output["reasoning_content"] = thinking_text.strip()

        # Add tool calls with results in OpenAI format for expandable tool UI
        tool_calls = turn.all_tool_calls()
        if tool_calls:
            output["tool_calls"] = []
            for tc in tool_calls:
                tool_call_entry: dict[str, Any] = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input) if tc.input else "{}",
                    },
                }
                # Include tool result as response if available
                if tc.result is not None:
                    tool_call_entry["response"] = {
                        "role": "tool",
                        "content": truncate(tc.result),
                        "tool_call_id": tc.id,
                    }
                output["tool_calls"].append(tool_call_entry)

        if interrupted:
            output["interrupted"] = True
            output["stop_reason"] = "user_interrupt"

        return output, assistant_text.strip(), thinking_text.strip()

    @staticmethod
    def build_subagent_inputs(
        prompt: str,
        agent_id: str | None = None,
        subagent_type: str | None = None,
    ) -> dict[str, Any]:
        """Build subagent inputs in ChatView-compatible format.

        Creates inputs with `messages` array for ChatView detection,
        similar to turn inputs.

        Args:
            prompt: The subagent's prompt/task description
            agent_id: Optional agent ID for metadata
            subagent_type: Optional subagent type from Task tool input

        Returns:
            Input dict with messages array for ChatView compatibility
        """
        inputs: dict[str, Any] = {
            # Anthropic-format messages for chat view detection
            "messages": [{"role": "user", "content": truncate(prompt, 5000)}],
        }
        if agent_id:
            inputs["agent_id"] = agent_id
        if subagent_type:
            inputs["subagent_type"] = subagent_type
        return inputs

    @staticmethod
    def build_subagent_output(
        session: Any,
    ) -> dict[str, Any]:
        """Build subagent output in Message format for ChatView.

        Aggregates assistant text and tool calls across all turns in the
        subagent session to create a unified output.

        Args:
            session: Parsed subagent session with turns

        Returns:
            Output dict in Message format with role, content, tool_calls
        """
        if not session or not session.turns:
            return {
                "role": "assistant",
                "content": "",
                "model": "unknown",
            }

        # Get final assistant response (from last turn's last message)
        final_output = ""
        if session.turns:
            last_turn = session.turns[-1]
            if last_turn.assistant_messages:
                final_output = last_turn.assistant_messages[-1].get_text() or ""

        # Collect all tool calls across all turns
        all_tool_calls = []
        for turn in session.turns:
            for tc in turn.all_tool_calls():
                tool_call_entry: dict[str, Any] = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input) if tc.input else "{}",
                    },
                }
                if tc.result is not None:
                    tool_call_entry["response"] = {
                        "role": "tool",
                        "content": truncate(tc.result),
                        "tool_call_id": tc.id,
                    }
                all_tool_calls.append(tool_call_entry)

        # Build Message format output
        model = session.primary_model()
        output: dict[str, Any] = {
            "role": "assistant",
            "content": truncate(final_output),
            "model": model or "unknown",
        }

        if all_tool_calls:
            output["tool_calls"] = all_tool_calls

        return output

    def finish_turn_call(
        self,
        turn_call: Any,
        turn: Any,
        session: Any,
        turn_index: int,
        *,
        interrupted: bool = False,
        extra_file_snapshots: list[Any] | None = None,
        ended_at: datetime | None = None,
    ) -> str | None:
        """Finish turn call with output, summary, and diff view.

        Args:
            turn_call: The call to finish
            turn: Parsed turn data
            session: Full session (for diff context)
            turn_index: 0-based index into session.turns
            interrupted: True if user interrupted this turn
            extra_file_snapshots: Additional snapshots (e.g., from subagents)
            ended_at: Optional timestamp override for retroactive logging

        Returns:
            Extracted question from response (for Q&A tracking), or None
        """
        usage = turn.total_usage()
        model = turn.primary_model()

        # Build output using shared helper
        output, assistant_text, _ = self.build_turn_output(turn, interrupted=interrupted)

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
        self.client.finish_call(turn_call, output=output, ended_at=ended_at)

        # Extract and return pending question context for next turn
        # If a question is detected, return the full assistant text for context
        # (not just the question line) - this gives the next turn full context
        if not interrupted:
            question = extract_question_from_text(assistant_text)
            if question:
                # Return full assistant text as Q&A context
                return assistant_text
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
        from weave.integrations.claude_plugin.views.diff_view import (
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
                cwd=session.cwd,
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
        ended_at: datetime | None = None,
    ) -> None:
        """Finish session call with summary, file snapshots, and diff view.

        Args:
            session_call: The call to finish (may be reconstructed)
            session: Parsed session data
            sessions_dir: Directory containing session files (for subagent lookup)
            end_reason: Optional reason (e.g., "user_exit", "timeout")
            extra_summary: Additional summary fields (compaction_count, redacted_secrets)
            ended_at: Optional timestamp override for retroactive logging
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
        self.client.finish_call(session_call, output=output, ended_at=ended_at)

    def _attach_session_diff_view(
        self,
        session_call: Any,
        session: Any,
        sessions_dir: Path,
    ) -> None:
        """Generate and attach session-level diff HTML view."""
        from weave.integrations.claude_plugin.views.diff_view import (
            generate_session_diff_html,
        )

        # Try file-history-based diff
        diff_html = generate_session_diff_html(
            session,
            cwd=session.cwd,
            sessions_dir=sessions_dir,
            project=self.project,
            first_prompt=session.first_user_prompt(),
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
