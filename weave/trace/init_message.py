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


def assert_min_weave_version(
    min_required_version: str, trace_server_host: str = "https://trace.wandb.ai"
) -> None:
    import weave

    if _parse_version(min_required_version) > _parse_version(weave.__version__):
        message = (
            f"The target Weave host {trace_server_host} requires a `weave` package version >= {min_required_version}."
            " To resolve, either:\n"
            "   * Upgrade `weave` by running: `pip install weave --upgrade`.\n"
            "   * Disable logging by omitting calls to `weave.init`."
        )
        raise ValueError(message)


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
