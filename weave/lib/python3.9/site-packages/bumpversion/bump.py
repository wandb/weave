"""Version changing methods."""

import shlex
from pathlib import Path
from typing import TYPE_CHECKING, List, MutableMapping, Optional

from bumpversion.hooks import run_post_commit_hooks, run_pre_commit_hooks, run_setup_hooks

if TYPE_CHECKING:  # pragma: no-coverage
    from bumpversion.files import ConfiguredFile
    from bumpversion.versioning.models import Version

from bumpversion.config import Config
from bumpversion.config.files import update_config_file
from bumpversion.config.files_legacy import update_ini_config_file
from bumpversion.context import get_context
from bumpversion.exceptions import ConfigurationError
from bumpversion.ui import get_indented_logger
from bumpversion.utils import key_val_string

logger = get_indented_logger(__name__)


def get_next_version(
    current_version: "Version", config: Config, version_part: Optional[str], new_version: Optional[str]
) -> "Version":
    """
    Bump the version_part to the next value.

    Args:
        current_version: The current version
        config: The current configuration
        version_part: Optional part of the version to bump
        new_version: Optional specific version to bump to

    Returns:
        The new version

    Raises:
        ConfigurationError: If it can't generate the next version.
    """
    if new_version:
        logger.info("Attempting to set new version '%s'", new_version)
        logger.indent()
        next_version = config.version_config.parse(new_version)
    elif version_part:
        logger.info("Attempting to increment part '%s'", version_part)
        logger.indent()
        next_version = current_version.bump(version_part)
    else:
        raise ConfigurationError("Unable to get the next version.")

    logger.info("Values are now: %s", key_val_string(next_version.components))
    logger.dedent()
    return next_version


def do_bump(
    version_part: Optional[str],
    new_version: Optional[str],
    config: Config,
    config_file: Optional[Path] = None,
    dry_run: bool = False,
) -> None:
    """
    Bump the version_part to the next value or set the version to new_version.

    Args:
        version_part: The name of the version component to bump
        new_version: The explicit version to set
        config: The configuration to use
        config_file: The configuration file to update
        dry_run: True if the operation should be a dry run
    """
    from bumpversion.files import modify_files, resolve_file_config

    logger.indent()

    ctx = get_context(config)

    logger.info("Parsing current version '%s'", config.current_version)
    logger.indent()
    version = config.version_config.parse(config.current_version)
    logger.dedent()

    run_setup_hooks(config, version, dry_run)

    next_version = get_next_version(version, config, version_part, new_version)
    next_version_str = config.version_config.serialize(next_version, ctx)
    logger.info("New version will be '%s'", next_version_str)

    if config.current_version == next_version_str:
        logger.info("Version is already '%s'", next_version_str)
        return

    logger.dedent()

    if dry_run:
        logger.info("Dry run active, won't touch any files.")

    ctx = get_context(config, version, next_version)

    configured_files = resolve_file_config(config.files_to_modify, config.version_config)

    if version_part:
        # filter the files that are not valid for this bump
        configured_files = [file for file in configured_files if version_part in file.file_change.include_bumps]
        configured_files = [file for file in configured_files if version_part not in file.file_change.exclude_bumps]

    modify_files(configured_files, version, next_version, ctx, dry_run)
    if config_file and config_file.suffix in {".cfg", ".ini"}:
        update_ini_config_file(config_file, config.current_version, next_version_str, dry_run)  # pragma: no-coverage
    else:
        update_config_file(config_file, config, version, next_version, ctx, dry_run)

    ctx = get_context(config, version, next_version)
    ctx["new_version"] = next_version_str

    run_pre_commit_hooks(config, version, next_version, dry_run)

    commit_and_tag(config, config_file, configured_files, ctx, dry_run)

    run_post_commit_hooks(config, version, next_version, dry_run)

    logger.info("Done.")


def commit_and_tag(
    config: Config,
    config_file: Optional[Path],
    configured_files: List["ConfiguredFile"],
    ctx: MutableMapping,
    dry_run: bool = False,
) -> None:
    """
    Commit and tag the changes if a tool is configured.

    Args:
        config: The configuration
        config_file: The configuration file to include in the commit, if it exists
        configured_files: A list of files to commit
        ctx: The context used to render the tag and tag message
        dry_run: True if the operation should be a dry run
    """
    if not config.scm_info.tool:
        return

    extra_args = shlex.split(config.commit_args) if config.commit_args else []

    commit_files = {f.file_change.filename for f in configured_files}
    if config_file:
        commit_files |= {str(config_file)}

    config.scm_info.tool.commit_to_scm(list(commit_files), config, ctx, extra_args, dry_run)
    config.scm_info.tool.tag_in_scm(config, ctx, dry_run)
