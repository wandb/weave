"""Tests for the netrc module.

This module contains comprehensive tests for the netrc utilities including
the Netrc class, helper functions, and edge cases.
"""

import netrc
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from weave.compat.wandb.util.netrc import Netrc, check_netrc_access, get_netrc_file_path


@pytest.fixture
def temp_netrc(tmp_path):
    netrc_path = tmp_path / ".netrc"
    return Netrc(netrc_path)


# Tests for Netrc class
@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        (None, Path.home() / ".netrc"),
        ("/custom/path/.netrc", Path("/custom/path/.netrc")),
    ],
)
def test_netrc_init_path(arg, expected):
    """Init resolves both the default and a custom path."""
    netrc = Netrc() if arg is None else Netrc(arg)
    assert netrc.path == expected


def test_netrc_read_nonexistent_file(temp_netrc):
    """Test reading a non-existent netrc file."""
    with pytest.raises(FileNotFoundError, match="Netrc file not found"):
        temp_netrc.read()


def test_netrc_read_malformed_file(temp_netrc):
    """Test reading a malformed netrc file."""
    # Create a malformed netrc file
    malformed_content = "invalid netrc content"
    temp_netrc.path.write_text(malformed_content)

    with pytest.raises(netrc.NetrcParseError):
        temp_netrc.read()


def test_netrc_read_valid_file(temp_netrc):
    """Test reading a valid netrc file."""
    # Create a test netrc file
    netrc_content = """machine example.com
  login testuser
  password testpass

machine api.example.com
  login apiuser
  account testaccount
  password apipass
"""
    temp_netrc.path.write_text(netrc_content)

    credentials = temp_netrc.read()
    assert credentials == {
        "example.com": {
            "login": "testuser",
            "account": "",
            "password": "testpass",
        },
        "api.example.com": {
            "login": "apiuser",
            "account": "testaccount",
            "password": "apipass",
        },
    }


def test_netrc_write_credentials(temp_netrc):
    """Test writing credentials to netrc file."""
    credentials = {
        "example.com": {
            "login": "testuser",
            "account": "testaccount",
            "password": "testpass",
        },
        "api.example.com": {
            "login": "apiuser",
            "account": "",
            "password": "apipass",
        },
    }

    temp_netrc.write(credentials)

    # Verify file was created
    assert temp_netrc.path.exists()

    # Check file permissions (should be 0o600). POSIX-only — Windows ignores
    # chmod for these mode bits.
    if sys.platform != "win32":
        file_stat = temp_netrc.path.stat()
        assert file_stat.st_mode & 0o777 == 0o600

    # Verify content by reading it back
    written_credentials = temp_netrc.read()
    assert written_credentials == credentials


def test_netrc_write_creates_parent_directory(tmp_path):
    """Test that write creates parent directories if they don't exist."""
    nested_path = tmp_path / "nested" / "dir" / ".netrc"
    netrc = Netrc(str(nested_path))

    credentials = {
        "example.com": {
            "login": "testuser",
            "account": "",
            "password": "testpass",
        }
    }

    netrc.write(credentials)

    assert nested_path.exists()
    assert nested_path.parent.exists()


@patch("os.chmod")
def test_netrc_write_permission_error(mock_chmod, temp_netrc):
    """Test write method when chmod fails."""
    mock_chmod.side_effect = OSError("Permission denied")

    credentials = {
        "example.com": {
            "login": "testuser",
            "account": "",
            "password": "testpass",
        }
    }

    with pytest.raises(PermissionError, match="Unable to write to netrc file"):
        temp_netrc.write(credentials)


def test_netrc_add_or_update_entry(temp_netrc):
    """add_or_update creates a new file, appends to an existing one, and updates in place."""
    # New file: full entry incl. account.
    temp_netrc.add_or_update_entry("example.com", "testuser", "testpass", "testaccount")
    assert temp_netrc.read() == {
        "example.com": {
            "login": "testuser",
            "account": "testaccount",
            "password": "testpass",
        }
    }

    # Append a second machine (no account) to the existing file.
    temp_netrc.add_or_update_entry("api.example.com", "apiuser", "apipass")
    credentials = temp_netrc.read()
    assert len(credentials) == 2
    assert credentials["example.com"]["login"] == "testuser"
    assert credentials["api.example.com"] == {
        "login": "apiuser",
        "account": "",
        "password": "apipass",
    }

    # Update the existing machine in place.
    temp_netrc.add_or_update_entry("example.com", "newuser", "newpass", "newaccount")
    credentials = temp_netrc.read()
    assert len(credentials) == 2
    assert credentials["example.com"] == {
        "login": "newuser",
        "account": "newaccount",
        "password": "newpass",
    }


def test_netrc_delete_entry(temp_netrc):
    """delete_entry removes a present machine, no-ops on a missing one, and no-ops with no file."""
    # No file yet -> False.
    assert temp_netrc.delete_entry("example.com") is False

    temp_netrc.write(
        {
            "example.com": {"login": "user1", "account": "", "password": "pass1"},
            "api.example.com": {"login": "user2", "account": "", "password": "pass2"},
        }
    )

    # Delete a present machine -> True, others retained.
    assert temp_netrc.delete_entry("example.com") is True
    credentials = temp_netrc.read()
    assert "example.com" not in credentials
    assert "api.example.com" in credentials

    # Delete a missing machine -> False, nothing changed.
    assert temp_netrc.delete_entry("nonexistent.com") is False
    credentials = temp_netrc.read()
    assert len(credentials) == 1
    assert "api.example.com" in credentials


def test_netrc_get_credentials(temp_netrc):
    """get_credentials returns the entry for a present machine, None otherwise."""
    # No file yet -> None.
    assert temp_netrc.get_credentials("example.com") is None

    temp_netrc.write(
        {
            "example.com": {
                "login": "testuser",
                "account": "testaccount",
                "password": "testpass",
            }
        }
    )

    assert temp_netrc.get_credentials("example.com") == {
        "login": "testuser",
        "account": "testaccount",
        "password": "testpass",
    }
    assert temp_netrc.get_credentials("nonexistent.com") is None


def test_netrc_list_machines(temp_netrc):
    """list_machines reflects file entries, empty file, and a missing file."""
    # No file yet -> empty.
    assert temp_netrc.list_machines() == []

    temp_netrc.write(
        {
            "example.com": {"login": "user1", "account": "", "password": "pass1"},
            "api.example.com": {"login": "user2", "account": "", "password": "pass2"},
        }
    )
    machines = temp_netrc.list_machines()
    assert len(machines) == 2
    assert "example.com" in machines
    assert "api.example.com" in machines

    # Empty file -> empty.
    temp_netrc.write({})
    assert temp_netrc.list_machines() == []


# Tests for netrc permission checking
@pytest.mark.parametrize(
    ("mode", "exists", "read_access", "write_access"),
    [
        (None, False, True, True),  # missing file: can create -> read/write True
        (0o600, True, True, True),  # read-write file
        (0o400, True, True, False),  # read-only file
    ],
)
def test_check_netrc_access(tmp_path, mode, exists, read_access, write_access):
    """check_netrc_access reports existence and read/write for missing, rw, and ro files."""
    netrc_path = tmp_path / ".netrc"
    if mode is not None:
        netrc_path.write_text("test content")
        os.chmod(netrc_path, mode)

    permissions = check_netrc_access(str(netrc_path))

    assert permissions.exists is exists
    assert permissions.read_access is read_access
    assert permissions.write_access is write_access


@pytest.mark.disable_logging_error_check(
    reason="This test is expected to raise OSError"
)
@patch("os.stat")
def test_check_netrc_access_os_error(mock_stat, tmp_path):
    """Test checking access when os.stat raises an OSError."""
    mock_stat.side_effect = OSError("Access denied")
    netrc_path = tmp_path / ".netrc"

    permissions = check_netrc_access(str(netrc_path))

    assert permissions.exists is False
    assert permissions.read_access is False
    assert permissions.write_access is False


# Tests for get_netrc_file_path function
@pytest.mark.parametrize(
    ("env_value", "expected"),
    [
        ("/custom/netrc/path", Path("/custom/netrc/path")),  # literal env path
        ("~/custom/netrc", Path("~/custom/netrc").expanduser()),  # tilde expansion
    ],
)
def test_get_netrc_file_path_from_env(env_value, expected):
    """NETRC env var wins and is user-expanded."""
    with patch.dict(os.environ, {"NETRC": env_value}):
        assert Path(get_netrc_file_path()) == expected


@patch.dict(os.environ, {}, clear=True)
def test_get_netrc_file_path_existing_file(tmp_path):
    """With no env var, an existing home .netrc is returned."""
    netrc_path = tmp_path / ".netrc"
    netrc_path.write_text("test")

    with patch("pathlib.Path.home", return_value=tmp_path):
        path = get_netrc_file_path()
        assert path == str(netrc_path)


@pytest.mark.parametrize(
    ("system", "home", "expected"),
    [
        ("Linux", Path("/home/user"), Path("/home/user/.netrc")),
        ("Windows", Path("C:/Users/user"), Path("C:/Users/user/_netrc")),
    ],
)
def test_get_netrc_file_path_default(system, home, expected):
    """With no env var and no existing file, the platform default name is used."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("platform.system", return_value=system),
        patch("pathlib.Path.home", return_value=home),
    ):
        assert Path(get_netrc_file_path()) == expected
