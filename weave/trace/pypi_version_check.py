"""
This module contains code for checking if there is a new version of a PyPI package available.

It is a modified version of the code from the wandb library, located at:
https://github.com/wandb/client/blob/main/wandb/sdk/internal/update.py

Copied here to avoid a dependency on the wandb library and allow more pointed control
over the version checking logic.
"""

from __future__ import annotations

import queue
import sys
import threading
from typing import TYPE_CHECKING, Any, Callable

import requests

if TYPE_CHECKING:
    import packaging.version  # type: ignore[import-not-found]


def check_available(
    current_version: str, module_name: str
) -> dict[str, str | None] | None:
    """
    Check if there is a new version of the module available on PyPI.

    Args:
        current_version (str): The current version of the module.
        module_name (str): The name of the module to check for updates.

    Returns:
        dict[str, str | None] | None: A dictionary containing the upgrade message, yank message, or delete message, or None if no update is available.
    """
    package_info = _find_available(current_version, module_name)
    if not package_info:
        return None

    latest_version, pip_prerelease, deleted, yanked, yanked_reason = package_info
    upgrade_message = (
        "{} version {} is available!  To upgrade, please run:\n"
        " $ pip install {} --upgrade{}".format(
            module_name,
            latest_version,
            module_name,
            " --pre" if pip_prerelease else "",
        )
    )
    delete_message = None
    if deleted:
        delete_message = f"{module_name} version {current_version} has been retired!  Please upgrade."
    yank_message = None
    if yanked:
        reason_message = f"({yanked_reason})  " if yanked_reason else ""
        yank_message = f"{module_name} version {current_version} has been recalled!  {reason_message}Please upgrade."

    # A new version is available!
    return {
        "upgrade_message": upgrade_message,
        "yank_message": yank_message,
        "delete_message": delete_message,
    }


def _parse_version(version: str) -> packaging.version.Version:
    """Parse a version string into a version object.

    This function is a wrapper around the `packaging.version.parse` function, which
    is used to parse version strings into version objects. If the `packaging` library
    is not installed, it falls back to the `pkg_resources` library.
    """
    try:
        from packaging.version import parse as parse_version  # type: ignore
    except ImportError:
        from pkg_resources import parse_version  # type: ignore[assignment]

    return parse_version(version)


def _async_call(target: Callable, timeout: int | float | None = None) -> Callable:
    """Wrap a method to run in the background with an optional timeout.

    Returns a new method that will call the original with any args, waiting for upto
    timeout seconds. This new method blocks on the original and returns the result or
    None if timeout was reached, along with the thread. You can check thread.is_alive()
    to determine if a timeout was reached. If an exception is thrown in the thread, we
    reraise it.
    """
    q: queue.Queue = queue.Queue()

    def wrapped_target(q: queue.Queue, *args: Any, **kwargs: Any) -> Any:
        try:
            q.put(target(*args, **kwargs))
        except Exception as e:
            q.put(e)

    def wrapper(*args: Any, **kwargs: Any) -> tuple[Exception | None, threading.Thread]:
        thread = threading.Thread(
            target=wrapped_target, args=(q,) + args, kwargs=kwargs
        )
        thread.daemon = True
        thread.start()
        try:
            result = q.get(True, timeout)
            if isinstance(result, Exception):
                raise result.with_traceback(sys.exc_info()[2])
        except queue.Empty:
            return None, thread
        else:
            return result, thread

    return wrapper


def _find_available(
    current_version: str, module_name: str
) -> tuple[str, bool, bool, bool, str | None] | None:
    pypi_url = f"https://pypi.org/pypi/{module_name}/json"
    yanked_dict = {}
    try:
        async_requests_get = _async_call(requests.get, timeout=5)
        data, thread = async_requests_get(pypi_url, timeout=3)
        if not data or isinstance(data, Exception):
            return None
        data = data.json()
        latest_version = data["info"]["version"]
        release_list = data["releases"].keys()
        for version, fields in data["releases"].items():
            for item in fields:
                yanked = item.get("yanked")
                yanked_reason = item.get("yanked_reason")
                if yanked:
                    yanked_dict[version] = yanked_reason
    except Exception:
        # Any issues whatsoever, just skip the latest version check.
        return None

    # Return if no update is available
    pip_prerelease = False
    deleted = False
    yanked = False
    yanked_reason = None
    parsed_current_version = _parse_version(current_version)

    # Check if current version has been yanked or deleted
    # NOTE: we will not return yanked or deleted if there is nothing to upgrade to
    if current_version in release_list:
        yanked = current_version in yanked_dict
        yanked_reason = yanked_dict.get(current_version)
    else:
        deleted = True

    # Check pre-releases
    if _parse_version(latest_version) <= parsed_current_version:
        # pre-releases are not included in latest_version
        # so if we are currently running a pre-release we check more
        if not parsed_current_version.is_prerelease:
            return None
        # Candidates are pre-releases with the same base_version
        release_list = map(_parse_version, release_list)
        release_list = filter(lambda v: v.is_prerelease, release_list)
        release_list = filter(
            lambda v: v.base_version == parsed_current_version.base_version,
            release_list,
        )
        release_list = sorted(release_list)
        if not release_list:
            return None

        parsed_latest_version = release_list[-1]
        if parsed_latest_version <= parsed_current_version:
            return None
        latest_version = str(parsed_latest_version)
        pip_prerelease = True

    return latest_version, pip_prerelease, deleted, yanked, yanked_reason
