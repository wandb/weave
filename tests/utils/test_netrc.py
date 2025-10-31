"""Tests for the netrc module.

This module contains comprehensive tests for the netrc utilities including
the Netrc class, helper functions, and edge cases.
"""

import netrc
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from weave.compat.wandb.util.netrc import Netrc, check_netrc_access, get_netrc_file_path


@pytest.fixture
def temp_netrc(tmp_path):
    netrc_path = tmp_path / ".netrc"
    return Netrc(netrc_path)


# Tests for Netrc class
def test_netrc_init_default_path():
    """Test initialization with default path."""
    netrc = Netrc()
    expected_path = Path.home() / ".netrc"
    assert netrc.path == expected_path


def test_netrc_init_custom_path():
    """Test initialization with custom path."""
    custom_path = "/custom/path/.netrc"
    netrc = Netrc(custom_path)
    assert netrc.path == Path(custom_path)


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

    # Check file permissions (should be 0o600)
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


def test_netrc_add_or_update_entry_new_file(temp_netrc):
    """Test adding entry to a new netrc file."""
    temp_netrc.add_or_update_entry("example.com", "testuser", "testpass", "testaccount")

    credentials = temp_netrc.read()
    assert len(credentials) == 1
    assert credentials["example.com"]["login"] == "testuser"
    assert credentials["example.com"]["password"] == "testpass"
    assert credentials["example.com"]["account"] == "testaccount"


def test_netrc_add_or_update_entry_existing_file(temp_netrc):
    """Test adding entry to an existing netrc file."""
    # Create initial file
    initial_credentials = {
        "example.com": {"login": "olduser", "account": "", "password": "oldpass"}
    }
    temp_netrc.write(initial_credentials)

    # Add new entry
    temp_netrc.add_or_update_entry("api.example.com", "apiuser", "apipass")

    credentials = temp_netrc.read()
    assert len(credentials) == 2
    assert credentials["example.com"]["login"] == "olduser"
    assert credentials["api.example.com"]["login"] == "apiuser"


def test_netrc_add_or_update_entry_update_existing(temp_netrc):
    """Test updating an existing entry."""
    # Create initial file
    initial_credentials = {
        "example.com": {"login": "olduser", "account": "", "password": "oldpass"}
    }
    temp_netrc.write(initial_credentials)

    # Update existing entry
    temp_netrc.add_or_update_entry("example.com", "newuser", "newpass", "newaccount")

    credentials = temp_netrc.read()
    assert len(credentials) == 1
    assert credentials["example.com"]["login"] == "newuser"
    assert credentials["example.com"]["password"] == "newpass"
    assert credentials["example.com"]["account"] == "newaccount"


def test_netrc_delete_entry_existing(temp_netrc):
    """Test deleting an existing entry."""
    # Create initial file with multiple entries
    initial_credentials = {
        "example.com": {"login": "user1", "account": "", "password": "pass1"},
        "api.example.com": {"login": "user2", "account": "", "password": "pass2"},
    }
    temp_netrc.write(initial_credentials)

    # Delete one entry
    result = temp_netrc.delete_entry("example.com")

    assert result is True
    credentials = temp_netrc.read()
    assert len(credentials) == 1
    assert "example.com" not in credentials
    assert "api.example.com" in credentials


def test_netrc_delete_entry_nonexistent(temp_netrc):
    """Test deleting a non-existent entry."""
    # Create initial file
    initial_credentials = {
        "example.com": {"login": "user1", "account": "", "password": "pass1"}
    }
    temp_netrc.write(initial_credentials)

    # Try to delete non-existent entry
    result = temp_netrc.delete_entry("nonexistent.com")

    assert result is False
    credentials = temp_netrc.read()
    assert len(credentials) == 1
    assert "example.com" in credentials


def test_netrc_delete_entry_no_file(temp_netrc):
    """Test deleting entry when netrc file doesn't exist."""
    result = temp_netrc.delete_entry("example.com")
    assert result is False


def test_netrc_get_credentials_existing(temp_netrc):
    """Test getting credentials for an existing machine."""
    credentials = {
        "example.com": {
            "login": "testuser",
            "account": "testaccount",
            "password": "testpass",
        }
    }
    temp_netrc.write(credentials)

    result = temp_netrc.get_credentials("example.com")

    assert result is not None
    assert result["login"] == "testuser"
    assert result["account"] == "testaccount"
    assert result["password"] == "testpass"


def test_netrc_get_credentials_nonexistent(temp_netrc):
    """Test getting credentials for a non-existent machine."""
    credentials = {
        "example.com": {"login": "testuser", "account": "", "password": "testpass"}
    }
    temp_netrc.write(credentials)

    result = temp_netrc.get_credentials("nonexistent.com")
    assert result is None


def test_netrc_get_credentials_no_file(temp_netrc):
    """Test getting credentials when netrc file doesn't exist."""
    result = temp_netrc.get_credentials("example.com")
    assert result is None


def test_netrc_list_machines_with_entries(temp_netrc):
    """Test listing machines when netrc file has entries."""
    credentials = {
        "example.com": {"login": "user1", "account": "", "password": "pass1"},
        "api.example.com": {"login": "user2", "account": "", "password": "pass2"},
    }
    temp_netrc.write(credentials)

    machines = temp_netrc.list_machines()

    assert len(machines) == 2
    assert "example.com" in machines
    assert "api.example.com" in machines


def test_netrc_list_machines_empty_file(temp_netrc):
    """Test listing machines when netrc file is empty."""
    temp_netrc.write({})

    machines = temp_netrc.list_machines()
    assert len(machines) == 0


def test_netrc_list_machines_no_file(temp_netrc):
    """Test listing machines when netrc file doesn't exist."""
    machines = temp_netrc.list_machines()
    assert len(machines) == 0


# Tests for netrc permission checking
def test_check_netrc_access_nonexistent_file(tmp_path):
    """Test checking access for a non-existent file."""
    netrc_path = tmp_path / ".netrc"
    permissions = check_netrc_access(str(netrc_path))

    assert permissions.exists is False
    assert permissions.read_access is True  # Can create
    assert permissions.write_access is True  # Can create


def test_check_netrc_access_existing_file(tmp_path):
    """Test checking access for an existing file."""
    # Create a test file with specific permissions
    netrc_path = tmp_path / ".netrc"
    netrc_path.write_text("test content")
    os.chmod(netrc_path, 0o600)

    permissions = check_netrc_access(str(netrc_path))

    assert permissions.exists is True
    assert permissions.read_access is True
    assert permissions.write_access is True


def test_check_netrc_access_read_only_file(tmp_path):
    """Test checking access for a read-only file."""
    # Create a test file with read-only permissions
    netrc_path = tmp_path / ".netrc"
    netrc_path.write_text("test content")
    os.chmod(netrc_path, 0o400)

    permissions = check_netrc_access(str(netrc_path))

    assert permissions.exists is True
    assert permissions.read_access is True
    assert permissions.write_access is False


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
@patch.dict(os.environ, {"NETRC": "/custom/netrc/path"})
def test_get_netrc_file_path_from_env():
    """Test getting netrc file path from environment variable."""
    path = get_netrc_file_path()
    assert path == "/custom/netrc/path"


@patch.dict(os.environ, {"NETRC": "~/custom/netrc"})
def test_get_netrc_file_path_expanduser():
    """Test getting netrc file path with user expansion."""
    path = get_netrc_file_path()
    expected = str(Path("~/custom/netrc").expanduser())
    assert path == expected


@patch.dict(os.environ, {}, clear=True)
def test_get_netrc_file_path_existing_file(tmp_path):
    """Test getting netrc file path when file exists."""
    netrc_path = tmp_path / ".netrc"
    netrc_path.write_text("test")

    with patch("pathlib.Path.home", return_value=tmp_path):
        path = get_netrc_file_path()
        assert path == str(netrc_path)


@patch.dict(os.environ, {}, clear=True)
@patch("platform.system", return_value="Linux")
def test_get_netrc_file_path_default_unix(mock_system):
    """Test getting default netrc file path on Unix systems."""
    with patch("pathlib.Path.home", return_value=Path("/home/user")):
        path = get_netrc_file_path()
        assert path == "/home/user/.netrc"


@patch.dict(os.environ, {}, clear=True)
@patch("platform.system", return_value="Windows")
def test_get_netrc_file_path_default_windows(mock_system):
    """Test getting default netrc file path on Windows systems."""
    with patch("pathlib.Path.home", return_value=Path("C:/Users/user")):
        path = get_netrc_file_path()
        assert path == "C:/Users/user/_netrc"
