"""Tests for Claude plugin teleport functionality."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestVerifyGitState:
    """Tests for verify_git_state function."""

    def test_returns_empty_errors_when_git_matches(self):
        """Should return empty errors when git state matches expected (in a clean repo)."""
        from weave.integrations.claude_plugin.teleport import verify_git_state
        from weave.integrations.claude_plugin.utils import get_git_info

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a clean git repo
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", "git@github.com:test/repo.git"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            # Create initial commit
            (Path(tmpdir) / "file.txt").write_text("content")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmpdir, capture_output=True)

            # Get current git info and verify
            current = get_git_info(tmpdir)
            errors, warnings = verify_git_state(current, tmpdir)
            assert len(errors) == 0

    def test_returns_error_when_not_git_repo(self):
        """Should return error when cwd is not a git repo."""
        from weave.integrations.claude_plugin.teleport import verify_git_state

        with tempfile.TemporaryDirectory() as tmpdir:
            expected = {
                "remote": "git@github.com:test/repo.git",
                "branch": "main",
                "commit": "abc123",
            }
            errors, warnings = verify_git_state(expected, tmpdir)
            assert len(errors) > 0
            assert any("not a git repository" in e.lower() for e in errors)

    def test_returns_error_when_remote_mismatch(self):
        """Should return error when git remote doesn't match."""
        from weave.integrations.claude_plugin.teleport import verify_git_state

        cwd = "/Users/vanpelt/Development/weave"
        expected = {
            "remote": "git@github.com:wrong/repo.git",
            "branch": "main",
            "commit": "abc123",
        }
        errors, warnings = verify_git_state(expected, cwd)
        assert len(errors) > 0
        assert any("remote" in e.lower() for e in errors)

    def test_returns_error_when_repo_dirty(self):
        """Should return error when repo has uncommitted changes."""
        from weave.integrations.claude_plugin.teleport import verify_git_state

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a git repo with uncommitted changes
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", "git@github.com:test/repo.git"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

            # Create and commit a file
            (Path(tmpdir) / "file.txt").write_text("content")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmpdir, capture_output=True)

            # Create uncommitted change
            (Path(tmpdir) / "file.txt").write_text("modified")

            expected = {
                "remote": "git@github.com:test/repo.git",
                "branch": "main",
                "commit": "abc123",
            }
            errors, warnings = verify_git_state(expected, tmpdir)
            assert len(errors) > 0
            assert any("uncommitted" in e.lower() or "dirty" in e.lower() for e in errors)

    def test_returns_warning_when_commit_mismatch(self):
        """Should return warning when commit doesn't match (but not error)."""
        from weave.integrations.claude_plugin.teleport import verify_git_state
        from weave.integrations.claude_plugin.utils import get_git_info

        cwd = "/Users/vanpelt/Development/weave"
        current = get_git_info(cwd)

        expected = {
            "remote": current["remote"],
            "branch": current["branch"],
            "commit": "0000000000000000000000000000000000000000",  # Different commit
        }
        errors, warnings = verify_git_state(expected, cwd)
        # Commit mismatch should be warning, not error
        assert len(warnings) > 0
        assert any("commit" in w.lower() for w in warnings)


class TestNormalizeGitRemote:
    """Tests for normalizing git remote URLs."""

    def test_ssh_and_https_are_equivalent(self):
        """SSH and HTTPS URLs for same repo should be treated as equivalent."""
        from weave.integrations.claude_plugin.teleport import normalize_git_remote

        ssh_url = "git@github.com:wandb/weave.git"
        https_url = "https://github.com/wandb/weave.git"
        https_no_ext = "https://github.com/wandb/weave"

        assert normalize_git_remote(ssh_url) == normalize_git_remote(https_url)
        assert normalize_git_remote(ssh_url) == normalize_git_remote(https_no_ext)

    def test_different_repos_are_different(self):
        """Different repos should have different normalized URLs."""
        from weave.integrations.claude_plugin.teleport import normalize_git_remote

        url1 = "git@github.com:wandb/weave.git"
        url2 = "git@github.com:other/repo.git"

        assert normalize_git_remote(url1) != normalize_git_remote(url2)


class TestRestoreFiles:
    """Tests for restore_files function."""

    def test_writes_files_to_correct_paths(self):
        """Should write file contents to correct paths in cwd."""
        from weave.integrations.claude_plugin.teleport import restore_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock file snapshots
            mock_content = MagicMock()
            mock_content.to_bytes.return_value = b"file content"

            file_snapshots = {
                "src/app.py": mock_content,
                "tests/test_app.py": mock_content,
            }

            count = restore_files(file_snapshots, tmpdir)

            assert count == 2
            assert (Path(tmpdir) / "src/app.py").exists()
            assert (Path(tmpdir) / "tests/test_app.py").exists()
            assert (Path(tmpdir) / "src/app.py").read_bytes() == b"file content"

    def test_skips_session_jsonl(self):
        """Should not write session.jsonl to repo."""
        from weave.integrations.claude_plugin.teleport import restore_files

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_content = MagicMock()
            mock_content.to_bytes.return_value = b"content"

            file_snapshots = {
                "session.jsonl": mock_content,
                "src/app.py": mock_content,
            }

            count = restore_files(file_snapshots, tmpdir)

            assert count == 1
            assert not (Path(tmpdir) / "session.jsonl").exists()
            assert (Path(tmpdir) / "src/app.py").exists()

    def test_creates_parent_directories(self):
        """Should create parent directories as needed."""
        from weave.integrations.claude_plugin.teleport import restore_files

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_content = MagicMock()
            mock_content.to_bytes.return_value = b"content"

            file_snapshots = {
                "deeply/nested/path/file.py": mock_content,
            }

            count = restore_files(file_snapshots, tmpdir)

            assert count == 1
            assert (Path(tmpdir) / "deeply/nested/path/file.py").exists()


class TestDownloadSessionFile:
    """Tests for download_session_file function."""

    def test_writes_session_to_claude_projects_dir(self):
        """Should write session.jsonl to ~/.claude/projects/{encoded_path}/"""
        from weave.integrations.claude_plugin.teleport import download_session_file

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_content = MagicMock()
            mock_content.to_bytes.return_value = b'{"type": "user"}'

            # Use a mock claude dir in temp
            claude_dir = Path(tmpdir) / ".claude"

            session_id = "test-session-123"
            cwd = "/Users/test/project"

            with patch("weave.integrations.claude_plugin.teleport.CLAUDE_DIR", claude_dir):
                path = download_session_file(session_id, cwd, mock_content)

            assert path.exists()
            assert session_id in str(path)
            assert path.read_bytes() == b'{"type": "user"}'
