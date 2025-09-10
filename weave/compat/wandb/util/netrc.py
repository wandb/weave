"""Module for reading and writing to netrc files.

This module provides utilities for working with netrc files, which are used
to store login credentials for various network services.
"""

from __future__ import annotations

import dataclasses
import logging
import netrc
import os
import platform
import stat
from pathlib import Path
from typing import TypedDict

NETRC_FILES = {
    "default": ".netrc",
    "Windows": "_netrc",
}

logger = logging.getLogger(__name__)


class Credentials(TypedDict):
    """Represents credentials for a machine in a netrc file.

    Attributes:
        login (str): The login username.
        account (str): The account name (optional).
        password (str): The password.
    """

    login: str
    account: str
    password: str


class Netrc:
    """A class for managing netrc files with read and write capabilities.

    The netrc file format stores machine credentials in the following format:
    machine hostname login username password password_value
    """

    def __init__(self, path: str | Path | None = None):
        """Initialize the NetrcManager.

        Args:
            netrc_path (str | Path | None): Path to the netrc file. If None, uses default ~/.netrc
        """
        if path is None:
            self.path = Path.home() / ".netrc"
        else:
            self.path = Path(path)

    def read(self) -> dict[str, Credentials]:
        """Read and parse the netrc file.

        Returns:
            dict[str, Credentials]: Dictionary mapping machine names to
                Credentials dictionaries.

        Raises:
            FileNotFoundError: If the netrc file doesn't exist.
            netrc.NetrcParseError: If the netrc file is malformed.

        Examples:
            >>> manager = Netrc()
            >>> credentials = manager.read()
            >>> creds = credentials.get('example.com')
            >>> if creds:
            ...     print(f"Login: {creds['login']}")
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Netrc file not found at {self.path}")

        try:
            netrc_obj = netrc.netrc(str(self.path))
            result: dict[str, Credentials] = {}
            for machine, credentials in netrc_obj.hosts.items():
                login, account, password = credentials
                result[machine] = {
                    "login": login or "",
                    "account": account or "",
                    "password": password or "",
                }
        except netrc.NetrcParseError as e:
            raise netrc.NetrcParseError(
                f"Failed to parse netrc file: {self.path}"
            ) from e
        else:
            return result

    def write(self, credentials: dict[str, Credentials]) -> None:
        """Write credentials to the netrc file.

        Args:
            credentials (dict[str, Credentials]): Dictionary mapping machine names
                to Credentials dictionaries.

        Raises:
            PermissionError: If unable to write to the netrc file.

        Examples:
            >>> manager = NetrcManager()
            >>> creds = {'example.com': {'login': 'user', 'account': 'account', 'password': 'pass'}}
            >>> manager.write(creds)
        """
        try:
            # Ensure the parent directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)

            # Write the netrc file
            with open(self.path, "w") as f:
                for machine, creds in credentials.items():
                    f.write(f"machine {machine}\n")
                    f.write(f"  login {creds['login']}\n")
                    if creds["account"]:
                        f.write(f"  account {creds['account']}\n")
                    f.write(f"  password {creds['password']}\n")
                    f.write("\n")

            # Set appropriate permissions (readable/writable by owner only)
            os.chmod(self.path, 0o600)
        except OSError as e:
            raise PermissionError(f"Unable to write to netrc file: {self.path}") from e

    def add_or_update_entry(
        self, machine: str, login: str, password: str, account: str = ""
    ) -> None:
        """Add or update an entry in the netrc file.

        Args:
            machine (str): The machine/hostname.
            login (str): The login username.
            password (str): The password.
            account (str): The account name (optional).

        Examples:
            >>> manager = Netrc()
            >>> manager.add_or_update_entry('api.example.com', 'user', 'secret123')
        """
        try:
            credentials = self.read()
        except FileNotFoundError:
            credentials = {}

        credentials[machine] = {
            "login": login,
            "account": account,
            "password": password,
        }
        self.write(credentials)

    def delete_entry(self, machine: str) -> bool:
        """Remove an entry from the netrc file.

        Args:
            machine (str): The machine/hostname to remove.

        Returns:
            bool: True if the entry was removed, False if it didn't exist.

        Examples:
            >>> manager = Netrc()
            >>> removed = manager.delete_entry('old.example.com')
            >>> print(f"Entry removed: {removed}")
        """
        try:
            credentials = self.read()
        except FileNotFoundError:
            return False

        if machine in credentials:
            del credentials[machine]
            self.write(credentials)
            return True
        return False

    def get_credentials(self, machine: str) -> Credentials | None:
        """Get credentials for a specific machine.

        Args:
            machine (str): The machine/hostname.

        Returns:
            Credentials | None: Credentials dictionary or None if not found.

        Examples:
            >>> manager = Netrc()
            >>> creds = manager.get_credentials('api.example.com')
            >>> if creds:
            ...     print(f"Login: {creds['login']}")
        """
        try:
            credentials = self.read()
            return credentials.get(machine)
        except FileNotFoundError:
            return None

    def list_machines(self) -> list[str]:
        """List all machines in the netrc file.

        Returns:
            list[str]: List of machine names.

        Examples:
            >>> manager = Netrc()
            >>> machines = manager.list_machines()
            >>> print(f"Configured machines: {machines}")
        """
        try:
            credentials = self.read()
            return list(credentials.keys())
        except FileNotFoundError:
            return []


@dataclasses.dataclass(frozen=True)
class _NetrcPermissions:
    exists: bool
    read_access: bool
    write_access: bool


def check_netrc_access(netrc_path: str) -> _NetrcPermissions:
    """Check if we can read and write to the netrc file."""
    file_exists = False
    write_access = False
    read_access = False
    try:
        st = os.stat(netrc_path)
        file_exists = True
        write_access = bool(st.st_mode & stat.S_IWUSR)
        read_access = bool(st.st_mode & stat.S_IRUSR)
    except FileNotFoundError:
        # If the netrc file doesn't exist, we will create it.
        write_access = True
        read_access = True
    except OSError:
        logger.exception(f"Unable to read permissions for {netrc_path}")

    return _NetrcPermissions(
        exists=file_exists,
        write_access=write_access,
        read_access=read_access,
    )


def get_netrc_file_path() -> str:
    """Get the path to the netrc file.

    Returns:
        str: Path to the netrc file.

    Examples:
        >>> path = _get_netrc_file_path()
        >>> isinstance(path, str)
        True
    """
    if fp := os.getenv("NETRC"):
        return str(Path(fp).expanduser())

    for netrc_file in NETRC_FILES.values():
        home_dir = Path.home()
        netrc_path = home_dir / netrc_file
        if netrc_path.exists():
            return str(netrc_path)

    netrc_file = NETRC_FILES.get(platform.system(), NETRC_FILES["default"])
    return str(Path.home() / netrc_file)
