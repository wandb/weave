"""Utilities for capturing git repository state."""

import subprocess
from typing import TypedDict

# Cache git state per process since it's expensive to compute
_git_state_cache: GitState | None = None


class GitState(TypedDict, total=False):
    """Git repository state information."""

    branch: str | None
    commit_sha: str | None
    dirty: bool


def get_git_state(use_cache: bool = True) -> GitState:
    """Get the current git repository state.

    This function caches the git state per process since git operations can be expensive.
    The cache is shared across all calls within the same process.

    Args:
        use_cache: If True, returns cached git state if available. If False, always
                   recomputes the git state.

    Returns:
        A dictionary containing:
        - branch: The current git branch name (or None if not in a git repo)
        - commit_sha: The current commit SHA (or None if not in a git repo)
        - dirty: Whether the working directory has uncommitted changes (False if not in a git repo)
    """
    global _git_state_cache

    # Return cached state if available and requested
    if use_cache and _git_state_cache is not None:
        return _git_state_cache

    git_state: GitState = {}

    try:
        # Get the current branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if result.returncode == 0:
            git_state["branch"] = result.stdout.strip()

        # Get the current commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if result.returncode == 0:
            git_state["commit_sha"] = result.stdout.strip()

        # Check if the working directory is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if result.returncode == 0:
            git_state["dirty"] = bool(result.stdout.strip())

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        # Git not available or timeout - return empty state
        pass

    # Cache the result
    _git_state_cache = git_state
    return git_state
