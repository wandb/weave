"""Configuration management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from bumpversion.config.files import read_config_file
from bumpversion.config.models import Config
from bumpversion.exceptions import ConfigurationError
from bumpversion.ui import get_indented_logger

if TYPE_CHECKING:  # pragma: no-coverage
    from pathlib import Path

logger = get_indented_logger(__name__)

DEFAULTS = {
    "current_version": None,
    "parse": r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)",
    "serialize": ("{major}.{minor}.{patch}",),
    "search": "{current_version}",
    "replace": "{new_version}",
    "regex": False,
    "ignore_missing_version": False,
    "ignore_missing_files": False,
    "tag": False,
    "sign_tags": False,
    "tag_name": "v{new_version}",
    "tag_message": "Bump version: {current_version} → {new_version}",
    "allow_dirty": False,
    "commit": False,
    "message": "Bump version: {current_version} → {new_version}",
    "commit_args": None,
    "scm_info": None,
    "parts": {},
    "files": [],
    "setup_hooks": [],
    "pre_commit_hooks": [],
    "post_commit_hooks": [],
}


def set_config_defaults(parsed_config: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Apply the defaults to the parsed config."""
    config_dict = DEFAULTS.copy()

    # We want to strip out unrecognized key-values to avoid inadvertent issues
    config_dict.update({key: val for key, val in parsed_config.items() if key in DEFAULTS.keys()})

    allowed_overrides = set(DEFAULTS.keys())
    config_dict.update({key: val for key, val in overrides.items() if key in allowed_overrides})

    return config_dict


def get_configuration(config_file: Union[str, Path, None] = None, **overrides: Any) -> Config:
    """
    Return the configuration based on any configuration files and overrides.

    Args:
        config_file: An explicit configuration file to use, otherwise search for one
        **overrides: Specific configuration key-values to override in the configuration

    Returns:
        The configuration
    """
    from bumpversion.config.utils import get_all_file_configs, get_all_part_configs
    from bumpversion.scm import SCMInfo, SourceCodeManager, get_scm_info  # noqa: F401

    logger.info("Reading configuration")
    logger.indent()

    parsed_config = read_config_file(config_file) if config_file else {}
    config_dict = set_config_defaults(parsed_config, **overrides)

    # Set any missing version components
    config_dict["parts"] = get_all_part_configs(config_dict)

    # Set any missing file configuration
    config_dict["files"] = get_all_file_configs(config_dict)

    # Resolve the SCMInfo class for Pydantic's BaseSettings
    Config.model_rebuild()
    config = Config(**config_dict)  # type: ignore[arg-type]

    # Get the information about the SCM
    scm_info = get_scm_info(config.tag_name, config.parse)
    config.scm_info = scm_info

    # Update and verify the current_version
    config.current_version = check_current_version(config)

    logger.dedent()

    return config


def check_current_version(config: Config) -> str:
    """
    Returns the current version.

    If the current version is not specified in the config file, command line or env variable,
    it attempts to retrieve it via a tag.

    Args:
        config: The current configuration dictionary.

    Returns:
        The version number

    Raises:
        ConfigurationError: If it can't find the current version
    """
    current_version = config.current_version
    scm_info = config.scm_info

    if current_version is None and scm_info.current_version:
        return scm_info.current_version
    elif current_version and scm_info.current_version and current_version != scm_info.current_version:
        logger.warning(
            "Specified version (%s) does not match last tagged version (%s)",
            current_version,
            scm_info.current_version,
        )
        return current_version
    elif current_version:
        return current_version

    raise ConfigurationError("Unable to determine the current version.")
