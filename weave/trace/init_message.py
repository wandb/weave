from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from weave.trace import urls
from weave.utils.pypi_version_check import check_available

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import packaging.version  # type: ignore[import-not-found]


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


def _print_version_check() -> None:
    import weave

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
