from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import weave
from weave.trace import urls
from weave.utils.pypi_version_check import check_available

if TYPE_CHECKING:
    import packaging.version  # type: ignore[import-not-found]

try:
    import wandb
except ImportError:
    WANDB_AVAILABLE = False
else:
    WANDB_AVAILABLE = True

REQUIRED_WANDB_VERSION = "0.16.4"

logger = logging.getLogger(__name__)


def _parse_version(version: str) -> packaging.version.Version:
    """Parse a version string into a version object.

    This function is a wrapper around the `packaging.version.parse` function, which
    is used to parse version strings into version objects. If the `packaging` library
    is not installed, it falls back to the `pkg_resources` library.
    """
    try:
        from packaging.version import parse as parse_version  # type: ignore
    except ImportError:
        from pkg_resources import parse_version

    return parse_version(version)


def _print_wandb_version_check() -> None:
    if not WANDB_AVAILABLE:
        return

    if _parse_version(REQUIRED_WANDB_VERSION) > _parse_version(wandb.__version__):
        message = (
            "wandb version >= 0.16.4 is required.  To upgrade, please run:\n"
            " $ pip install wandb --upgrade"
        )
        logger.info(message)
        return

    wandb_messages = check_available(wandb.__version__, "wandb")
    if not wandb_messages:
        return

    use_message = (
        wandb_messages.get("delete_message")
        or wandb_messages.get("yank_message")
        or wandb_messages.get("upgrade_message")
    )
    if use_message:
        logger.info(use_message)


def _print_weave_version_check() -> None:
    weave_messages = check_available(weave.__version__, "weave")
    if not weave_messages:
        return

    use_message = (
        weave_messages.get("delete_message")
        or weave_messages.get("yank_message")
        or weave_messages.get("upgrade_message")
    )
    if use_message:
        logger.info(use_message)


def _print_version_check() -> None:
    _print_wandb_version_check()
    _print_weave_version_check()


def check_min_weave_version(
    min_required_version: str,
    trace_server_url: str,
) -> bool:
    """Check that the weave client version meets the server's minimum requirement.

    Args:
        min_required_version: The minimum weave version required by the server.
        trace_server_url: The trace server URL (for error messages).

    Returns:
        True if the client version is compatible, False otherwise.
        When False, a warning is logged and tracing should be disabled.
    """
    if _parse_version(min_required_version) > _parse_version(weave.__version__):
        message = (
            f"The target Weave host {trace_server_url} requires a `weave` package version >= {min_required_version}, "
            f"but you have version {weave.__version__}. "
            "Tracing will be disabled. "
            "To resolve, upgrade `weave` by running: `pip install weave --upgrade`."
        )
        logger.warning(message)
        return False
    return True


def check_min_trace_server_version(
    trace_server_version: str | None,
    min_required_version: str | None,
    trace_server_url: str,
) -> bool:
    """Check that the trace server version meets the client's minimum requirement.

    Args:
        trace_server_version: The version reported by the server, or None if not available.
        min_required_version: The minimum version required by this client, or None if no requirement.
        trace_server_url: The trace server URL (for error messages).

    Returns:
        True if the server version is compatible, False otherwise.
        When False, a warning is logged and tracing should be disabled.
    """
    # No requirement from client - compatible
    if min_required_version is None:
        return True

    # Client requires a version but server didn't report one (old server)
    if trace_server_version is None:
        message = (
            f"This client requires trace server version >= {min_required_version}, "
            f"but the server at {trace_server_url} does not report its version. "
            "Tracing will be disabled. "
            "Please contact your administrator to upgrade the trace server, or "
            "downgrade your `weave` package to a compatible version."
        )
        logger.warning(message)
        return False

    # Both versions available - compare them
    if _parse_version(min_required_version) > _parse_version(trace_server_version):
        message = (
            f"The trace server at {trace_server_url} is running version {trace_server_version}, "
            f"but this client requires version >= {min_required_version}. "
            "Tracing will be disabled. "
            "Please contact your administrator to upgrade the trace server, or "
            "downgrade your `weave` package to a compatible version."
        )
        logger.warning(message)
        return False

    return True


def print_init_message(
    username: str | None, entity_name: str, project_name: str, read_only: bool
) -> None:
    try:
        _print_version_check()
    except Exception as e:
        pass

    message = ""
    if username is not None:
        message += f"Logged in as Weights & Biases user: {username}.\n"
    message += (
        f"View Weave data at {urls.project_weave_root_url(entity_name, project_name)}"
    )
    # Cosmetically, if we are in `read_only` mode, we are not logging data, so
    # we should not print the message about logging data.
    if not read_only:
        logger.info(message)
