"""Teleport functionality for Claude Code sessions.

TODO: Add support for partial file restoration (allow user to select which files to restore)

Enables resuming a Claude session from a different machine by:
1. Fetching session data from Weave
2. Verifying git state matches
3. Restoring files to the local repo
4. Downloading session file for `claude --resume`

Usage:
    /weave:teleport <session_id>
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Claude's directory for project sessions
CLAUDE_DIR = Path.home() / ".claude"


def normalize_git_remote(url: str) -> str:
    """Normalize a git remote URL for comparison.

    Converts SSH and HTTPS URLs to a canonical form so that
    git@github.com:user/repo.git and https://github.com/user/repo.git
    are treated as equivalent.

    Args:
        url: Git remote URL (SSH or HTTPS format)

    Returns:
        Normalized URL in format "host:user/repo"
    """
    if not url:
        return ""

    # Remove .git suffix
    url = re.sub(r"\.git$", "", url)

    # SSH format: git@github.com:user/repo
    ssh_match = re.match(r"git@([^:]+):(.+)", url)
    if ssh_match:
        host, path = ssh_match.groups()
        return f"{host}:{path}"

    # HTTPS format: https://github.com/user/repo
    https_match = re.match(r"https?://([^/]+)/(.+)", url)
    if https_match:
        host, path = https_match.groups()
        return f"{host}:{path}"

    # Return as-is if no match
    return url


def verify_git_state(
    expected: dict[str, str], cwd: str
) -> tuple[list[str], list[str]]:
    """Verify that the current git state matches the expected state.

    Args:
        expected: Dict with 'remote', 'branch', 'commit' keys
        cwd: Working directory to check

    Returns:
        Tuple of (errors, warnings) where errors are blocking issues
        and warnings are non-blocking notices
    """
    from weave.integrations.claude_plugin.utils import get_git_info

    errors: list[str] = []
    warnings: list[str] = []

    # Check if cwd is a git repo
    current = get_git_info(cwd)
    if current is None:
        errors.append(f"'{cwd}' is not a git repository")
        return errors, warnings

    # Check remote matches
    expected_remote = normalize_git_remote(expected.get("remote", ""))
    current_remote = normalize_git_remote(current.get("remote", ""))

    if expected_remote != current_remote:
        errors.append(
            f"Remote mismatch. Expected '{expected.get('remote')}', "
            f"got '{current.get('remote')}'"
        )

    # Check for uncommitted changes
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            errors.append("Uncommitted changes detected. Commit or stash first.")
    except Exception as e:
        warnings.append(f"Could not check git status: {e}")

    # Check commit matches (warning only, not blocking)
    expected_commit = expected.get("commit", "")
    current_commit = current.get("commit", "")
    if expected_commit and current_commit and expected_commit != current_commit:
        warnings.append(
            f"Commit mismatch. Session was at '{expected_commit[:8]}...', "
            f"current is '{current_commit[:8]}...'"
        )

    # Check branch matches (warning only)
    expected_branch = expected.get("branch", "")
    current_branch = current.get("branch", "")
    if expected_branch and current_branch and expected_branch != current_branch:
        warnings.append(
            f"Branch mismatch. Session was on '{expected_branch}', "
            f"current is '{current_branch}'"
        )

    return errors, warnings


def _get_content_metadata(content: Any) -> dict[str, Any]:
    """Get metadata from a Content object or dict.

    When Content objects are fetched from Weave via get_calls(),
    they are returned as dicts, not Content instances.
    """
    if isinstance(content, dict):
        return content.get("metadata", {}) or {}
    return getattr(content, "metadata", {}) or {}


def _get_content_bytes(content: Any) -> bytes:
    """Get bytes from a Content object or dict.

    When Content objects are fetched from Weave via get_calls(),
    they are returned as dicts with 'data' as bytes or base64 string.
    """
    if isinstance(content, dict):
        data = content.get("data", b"")
        if isinstance(data, str):
            # Data may be base64 encoded
            import base64
            try:
                return base64.b64decode(data)
            except Exception:
                return data.encode("utf-8")
        return data if isinstance(data, bytes) else b""
    # Content objects store bytes in the .data attribute
    return content.data


def restore_files(
    file_snapshots: list[Any], cwd: str, skip_session_jsonl: bool = True
) -> int:
    """Restore files from snapshots to the working directory.

    Args:
        file_snapshots: List of Content objects with relative_path in metadata
        cwd: Working directory to restore files into
        skip_session_jsonl: If True, skip session.jsonl (default True)

    Returns:
        Number of files restored
    """
    cwd_path = Path(cwd)
    count = 0

    for content in file_snapshots:
        # Get relative path from metadata (handles both Content objects and dicts)
        metadata = _get_content_metadata(content)
        rel_path = metadata.get("relative_path", "")

        if not rel_path:
            logger.warning("File snapshot missing relative_path in metadata")
            continue

        # Skip session.jsonl - it goes elsewhere
        if skip_session_jsonl and rel_path == "session.jsonl":
            continue

        try:
            target_path = cwd_path / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content (handles both Content objects and dicts)
            file_bytes = _get_content_bytes(content)
            target_path.write_bytes(file_bytes)
            count += 1
            logger.debug(f"Restored file: {rel_path}")
        except Exception as e:
            logger.warning(f"Failed to restore {rel_path}: {e}")

    return count


def download_session_file(
    session_id: str, cwd: str, session_content: Any
) -> Path:
    """Download session.jsonl to Claude's projects directory.

    Claude stores sessions in ~/.claude/projects/{encoded_cwd}/{session_id}.jsonl

    Args:
        session_id: Session UUID
        cwd: Working directory (used to compute projects path)
        session_content: Content object with session.jsonl data

    Returns:
        Path where session file was written
    """
    # Encode cwd path for directory name (replace / with -)
    # Claude keeps the leading dash, e.g. /home/user/foo -> -home-user-foo
    encoded_cwd = cwd.replace("/", "-")

    # Create projects directory
    projects_dir = CLAUDE_DIR / "projects" / encoded_cwd
    projects_dir.mkdir(parents=True, exist_ok=True)

    # Write session file (handles both Content objects and dicts)
    session_path = projects_dir / f"{session_id}.jsonl"
    session_path.write_bytes(_get_content_bytes(session_content))

    logger.debug(f"Downloaded session file to: {session_path}")
    return session_path


def fetch_session_from_weave(
    session_id: str, project: str
) -> dict[str, Any] | None:
    """Fetch session data from Weave API.

    Args:
        session_id: Session UUID to fetch
        project: Weave project in "entity/project" format

    Returns:
        Dict with session data, or None if not found
    """
    import weave
    from weave.trace.context.weave_client_context import require_weave_client

    # Suppress init messages - set env var before init so logger is configured with WARNING level
    os.environ["WEAVE_LOG_LEVEL"] = "WARNING"
    weave.init(project)
    client = require_weave_client()

    # Query calls with session_id in attributes (more efficient than inputs)
    try:
        calls_iter = client.get_calls(
            # Query for session_id in attributes using $expr syntax
            query={
                "$expr": {
                    "$eq": [
                        {"$getField": "attributes.session_id"},
                        {"$literal": session_id}
                    ]
                }
            },
            limit=1,
        )

        # Convert iterator to list
        calls = list(calls_iter)

        if not calls:
            logger.warning(f"Session {session_id} not found in Weave")
            return None

        call = calls[0]
        return {
            "call_id": call.id,
            "inputs": dict(call.inputs) if call.inputs else {},
            "output": dict(call.output) if call.output else {},
            "summary": dict(call.summary) if call.summary else {},
            "attributes": dict(call.attributes) if call.attributes else {},
        }
    except Exception as e:
        logger.error(f"Failed to fetch session from Weave: {e}")
        return None


def teleport(
    session_id: str,
    cwd: str,
    project: str,
    skip_git_check: bool = False,
) -> tuple[bool, str]:
    """Teleport a Claude session to the current machine.

    Args:
        session_id: Session UUID to teleport
        cwd: Current working directory
        project: Weave project in "entity/project" format
        skip_git_check: If True, skip git verification (dangerous)

    Returns:
        Tuple of (success, message)
    """
    # Fetch session from Weave
    session_data = fetch_session_from_weave(session_id, project)
    if session_data is None:
        return False, f"Session {session_id} not found in Weave"

    output = session_data.get("output", {})
    summary = session_data.get("summary", {})

    # Check if session has ended (end_reason is in summary, not output)
    if not summary.get("end_reason"):
        return False, f"Session {session_id} is still active. Wait for it to end."

    # Verify git state (git info is in summary)
    git_info = summary.get("git", {})
    if not skip_git_check and git_info:
        errors, warnings = verify_git_state(git_info, cwd)

        if errors:
            return False, "Git verification failed:\n" + "\n".join(f"  - {e}" for e in errors)

        for warning in warnings:
            logger.warning(warning)

    # Get file snapshots from output (list of Content objects)
    file_snapshots = output.get("file_snapshots", [])
    if not file_snapshots:
        return False, "Session has no file snapshots to restore"

    # Find session.jsonl from the list (handles both Content objects and dicts)
    session_content = None
    for content in file_snapshots:
        metadata = _get_content_metadata(content)
        if metadata.get("relative_path") == "session.jsonl":
            session_content = content
            break

    if session_content:
        session_path = download_session_file(session_id, cwd, session_content)
    else:
        return False, "Session file (session.jsonl) not found in snapshots"

    # Restore files to repo
    file_count = restore_files(file_snapshots, cwd)

    # Success message
    message = f"""Teleport complete!

Restored {file_count} files to {cwd}
Session file: {session_path}

To resume the session, run:
  claude --resume {session_id}"""

    return True, message


def main() -> int:
    """CLI entry point for teleport command.

    Usage:
        python -m weave.integrations.claude_plugin.teleport <session_id> <project> [--cwd <path>] [--skip-git-check]
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Teleport a Claude Code session from Weave"
    )
    parser.add_argument("session_id", help="Session UUID to teleport")
    parser.add_argument("project", help="Weave project (entity/project)")
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Working directory (default: current directory)",
    )
    parser.add_argument(
        "--skip-git-check",
        action="store_true",
        help="Skip git verification (dangerous)",
    )

    args = parser.parse_args()

    success, message = teleport(
        session_id=args.session_id,
        cwd=args.cwd,
        project=args.project,
        skip_git_check=args.skip_git_check,
    )

    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
