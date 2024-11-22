"""General utilities."""

import string
import subprocess
from subprocess import CompletedProcess
from typing import Any, List, Optional, Tuple, Union

from bumpversion.exceptions import BumpVersionError
from bumpversion.ui import get_indented_logger

logger = get_indented_logger(__name__)


def extract_regex_flags(regex_pattern: str) -> Tuple[str, str]:
    """
    Extract the regex flags from the regex pattern.

    Args:
        regex_pattern: The pattern that might start with regex flags

    Returns:
        A tuple of the regex pattern without the flag string and regex flag string
    """
    import re

    flag_pattern = r"^(\(\?[aiLmsux]+\))"
    bits = re.split(flag_pattern, regex_pattern)
    return (regex_pattern, "") if len(bits) == 1 else (bits[2], bits[1])


def recursive_sort_dict(input_value: Any) -> Any:
    """Sort a dictionary recursively."""
    if not isinstance(input_value, dict):
        return input_value

    return {key: recursive_sort_dict(input_value[key]) for key in sorted(input_value.keys())}


def key_val_string(d: dict) -> str:
    """Render the dictionary as a comma-delimited key=value string."""
    return ", ".join(f"{k}={v}" for k, v in sorted(d.items()))


def labels_for_format(serialize_format: str) -> List[str]:
    """Return a list of labels for the given serialize_format."""
    return [item[1] for item in string.Formatter().parse(serialize_format) if item[1]]


def get_overrides(**kwargs) -> dict:
    """Return a dictionary containing only the overridden key-values."""
    return {key: val for key, val in kwargs.items() if val is not None}


def get_nested_value(d: dict, path: str) -> Any:
    """
    Retrieves the value of a nested key in a dictionary based on the given path.

    Args:
        d: The dictionary to search.
        path: A string representing the path to the nested key, separated by periods.

    Returns:
        The value of the nested key.

    Raises:
        KeyError: If a key in the path does not exist.
        ValueError: If an element in the path is not a dictionary.
    """
    keys = path.split(".")
    current_element = d

    for key in keys:
        if not isinstance(current_element, dict):
            raise ValueError(f"Element at '{'.'.join(keys[:keys.index(key)])}' is not a dictionary")

        if key not in current_element:
            raise KeyError(f"Key '{key}' not found at '{'.'.join(keys[:keys.index(key)])}'")

        current_element = current_element[key]

    return current_element


def set_nested_value(d: dict, value: Any, path: str) -> None:
    """
    Sets the value of a nested key in a dictionary based on the given path.

    Args:
        d: The dictionary to search.
        value: The value to set.
        path: A string representing the path to the nested key, separated by periods.

    Raises:
        ValueError: If an element in the path is not a dictionary.
        KeyError: If a key in the path does not exist.
    """
    keys = path.split(".")
    last_element = keys[-1]
    current_element = d

    for i, key in enumerate(keys):
        if key == last_element:
            current_element[key] = value
        elif key not in current_element:
            raise KeyError(f"Key '{key}' not found at '{'.'.join(keys[:keys.index(key)])}'")
        elif not isinstance(current_element[key], dict):
            raise ValueError(f"Path '{'.'.join(keys[:i + 1])}' does not lead to a dictionary.")
        else:
            current_element = current_element[key]


def format_and_raise_error(exc: Union[TypeError, subprocess.CalledProcessError]) -> None:
    """Format the error message from an exception and re-raise it as a BumpVersionError."""
    if isinstance(exc, subprocess.CalledProcessError):
        output = "\n".join([x for x in [exc.stdout, exc.stderr] if x])
        cmd = " ".join(exc.cmd)
        err_msg = f"Failed to run `{cmd}`: return code {exc.returncode}, output: {output}"
    else:  # pragma: no-coverage
        err_msg = f"Failed to run a command: {exc}"
    logger.exception(err_msg)
    raise BumpVersionError(err_msg) from exc


def run_command(command: list, env: Optional[dict] = None) -> CompletedProcess:
    """Run a shell command and return its output."""
    result = subprocess.run(command, text=True, check=True, capture_output=True, env=env)  # NOQA: S603
    result.check_returncode()
    return result
