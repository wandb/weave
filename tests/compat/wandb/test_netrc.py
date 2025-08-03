"""Tests for netrc utility functionality."""

from netrc import NetrcParseError
from pathlib import Path

import pytest

from weave.compat.wandb.util.netrc import Credentials, Netrc


def test_netrc_initialization_default_path():
    """Test Netrc initialization with default path."""
    netrc_manager = Netrc()
    expected_path = Path.home() / ".netrc"
    assert netrc_manager.path == expected_path


def test_netrc_initialization_custom_path():
    """Test Netrc initialization with custom path."""
    custom_path = "/tmp/custom_netrc"
    netrc_manager = Netrc(custom_path)
    assert netrc_manager.path == Path(custom_path)


def test_netrc_read_nonexistent_file(tmp_path):
    """Test reading from non-existent netrc file."""
    nonexistent_path = tmp_path / "nonexistent_netrc"
    netrc_manager = Netrc(nonexistent_path)

    with pytest.raises(FileNotFoundError):
        netrc_manager.read()


def test_netrc_write_and_read(tmp_path):
    """Test writing and reading netrc file."""
    netrc_path = tmp_path / "test_netrc"
    netrc_manager = Netrc(netrc_path)

    # Test data
    credentials = {
        "api.wandb.ai": {
            "login": "user",
            "account": "",
            "password": "test_api_key_123456789012345678901234567890",
        },
        "custom.wandb.server": {
            "login": "admin",
            "account": "team",
            "password": "custom_key_123456789012345678901234567890",
        },
    }

    # Write credentials
    netrc_manager.write(credentials)

    # Verify file exists and has correct permissions
    assert netrc_path.exists()
    stat_info = netrc_path.stat()
    # Check that file is readable/writable by owner only (0o600)
    assert stat_info.st_mode & 0o777 == 0o600

    # Read credentials back
    read_credentials = netrc_manager.read()

    assert len(read_credentials) == 2
    assert read_credentials["api.wandb.ai"]["login"] == "user"
    assert (
        read_credentials["api.wandb.ai"]["password"]
        == "test_api_key_123456789012345678901234567890"
    )
    assert read_credentials["custom.wandb.server"]["login"] == "admin"
    assert read_credentials["custom.wandb.server"]["account"] == "team"


def test_netrc_read_malformed_file(tmp_path):
    """Test reading malformed netrc file."""
    netrc_path = tmp_path / "malformed_netrc"

    # Write malformed content
    with open(netrc_path, "w") as f:
        f.write("machine incomplete")  # Missing required fields

    netrc_manager = Netrc(netrc_path)

    with pytest.raises(NetrcParseError):
        netrc_manager.read()


def test_netrc_add_or_update_entry_new_file(tmp_path):
    """Test adding entry to new netrc file."""
    netrc_path = tmp_path / "new_netrc"
    netrc_manager = Netrc(netrc_path)

    # Add entry to non-existent file
    netrc_manager.add_or_update_entry(
        "api.wandb.ai", "user", "test_api_key_123456789012345678901234567890"
    )

    # Verify file was created and entry exists
    assert netrc_path.exists()
    credentials = netrc_manager.read()

    assert "api.wandb.ai" in credentials
    assert credentials["api.wandb.ai"]["login"] == "user"
    assert (
        credentials["api.wandb.ai"]["password"]
        == "test_api_key_123456789012345678901234567890"
    )
    assert credentials["api.wandb.ai"]["account"] == ""


def test_netrc_add_or_update_entry_existing_file(tmp_path):
    """Test updating entry in existing netrc file."""
    netrc_path = tmp_path / "existing_netrc"
    netrc_manager = Netrc(netrc_path)

    # Create initial entry
    initial_credentials = {
        "api.wandb.ai": {
            "login": "old_user",
            "account": "",
            "password": "old_key_123456789012345678901234567890",
        }
    }
    netrc_manager.write(initial_credentials)

    # Update entry
    netrc_manager.add_or_update_entry(
        "api.wandb.ai",
        "new_user",
        "new_key_123456789012345678901234567890",
        "team_account",
    )

    # Verify entry was updated
    credentials = netrc_manager.read()

    assert credentials["api.wandb.ai"]["login"] == "new_user"
    assert (
        credentials["api.wandb.ai"]["password"]
        == "new_key_123456789012345678901234567890"
    )
    assert credentials["api.wandb.ai"]["account"] == "team_account"


def test_netrc_delete_entry_existing(tmp_path):
    """Test deleting existing entry from netrc file."""
    netrc_path = tmp_path / "test_netrc"
    netrc_manager = Netrc(netrc_path)

    # Create file with multiple entries
    credentials = {
        "api.wandb.ai": {
            "login": "user1",
            "account": "",
            "password": "key1_123456789012345678901234567890",
        },
        "custom.wandb.server": {
            "login": "user2",
            "account": "",
            "password": "key2_123456789012345678901234567890",
        },
    }
    netrc_manager.write(credentials)

    # Delete one entry
    result = netrc_manager.delete_entry("api.wandb.ai")

    assert result is True

    # Verify entry was deleted
    remaining_credentials = netrc_manager.read()

    assert "api.wandb.ai" not in remaining_credentials
    assert "custom.wandb.server" in remaining_credentials


def test_netrc_delete_entry_nonexistent(tmp_path):
    """Test deleting non-existent entry from netrc file."""
    netrc_path = tmp_path / "test_netrc"
    netrc_manager = Netrc(netrc_path)

    # Create file with one entry
    credentials = {
        "api.wandb.ai": {
            "login": "user",
            "account": "",
            "password": "key_123456789012345678901234567890",
        }
    }
    netrc_manager.write(credentials)

    # Try to delete non-existent entry
    result = netrc_manager.delete_entry("nonexistent.server")

    assert result is False

    # Verify existing entry is still there
    remaining_credentials = netrc_manager.read()
    assert "api.wandb.ai" in remaining_credentials


def test_netrc_delete_entry_no_file(tmp_path):
    """Test deleting entry when netrc file doesn't exist."""
    netrc_path = tmp_path / "nonexistent_netrc"
    netrc_manager = Netrc(netrc_path)

    # Try to delete from non-existent file
    result = netrc_manager.delete_entry("api.wandb.ai")

    assert result is False


def test_netrc_get_credentials_existing(tmp_path):
    """Test getting credentials for existing machine."""
    netrc_path = tmp_path / "test_netrc"
    netrc_manager = Netrc(netrc_path)

    # Create file with credentials
    credentials = {
        "api.wandb.ai": {
            "login": "test_user",
            "account": "test_account",
            "password": "test_key_123456789012345678901234567890",
        }
    }
    netrc_manager.write(credentials)

    # Get credentials
    result = netrc_manager.get_credentials("api.wandb.ai")

    assert result is not None
    assert result["login"] == "test_user"
    assert result["account"] == "test_account"
    assert result["password"] == "test_key_123456789012345678901234567890"


def test_netrc_get_credentials_nonexistent(tmp_path):
    """Test getting credentials for non-existent machine."""
    netrc_path = tmp_path / "test_netrc"
    netrc_manager = Netrc(netrc_path)

    # Create file with different credentials
    credentials = {
        "api.wandb.ai": {
            "login": "user",
            "account": "",
            "password": "key_123456789012345678901234567890",
        }
    }
    netrc_manager.write(credentials)

    # Try to get non-existent credentials
    result = netrc_manager.get_credentials("nonexistent.server")

    assert result is None


def test_netrc_get_credentials_no_file(tmp_path):
    """Test getting credentials when netrc file doesn't exist."""
    netrc_path = tmp_path / "nonexistent_netrc"
    netrc_manager = Netrc(netrc_path)

    # Try to get credentials from non-existent file
    result = netrc_manager.get_credentials("api.wandb.ai")

    assert result is None


def test_netrc_write_creates_parent_directory(tmp_path):
    """Test that write creates parent directories if they don't exist."""
    # Create nested path
    nested_path = tmp_path / "nested" / "dir" / "netrc"
    netrc_manager = Netrc(nested_path)

    # Write credentials (should create parent directories)
    credentials = {
        "api.wandb.ai": {
            "login": "user",
            "account": "",
            "password": "key_123456789012345678901234567890",
        }
    }
    netrc_manager.write(credentials)

    # Verify file and directories were created
    assert nested_path.exists()
    assert nested_path.parent.exists()

    # Verify credentials can be read back
    read_credentials = netrc_manager.read()
    assert "api.wandb.ai" in read_credentials


def test_credentials_typed_dict():
    """Test that Credentials TypedDict works as expected."""
    # This is mainly for type checking, but we can verify the structure
    credentials: Credentials = {
        "login": "test_user",
        "account": "test_account",
        "password": "test_password",
    }

    assert credentials["login"] == "test_user"
    assert credentials["account"] == "test_account"
    assert credentials["password"] == "test_password"
