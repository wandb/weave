"""Contains methods for finding and reading configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, MutableMapping, Union

from bumpversion.config.files_legacy import read_ini_file
from bumpversion.ui import get_indented_logger, print_warning

if TYPE_CHECKING:  # pragma: no-coverage
    from bumpversion.config.models import Config
    from bumpversion.versioning.models import Version

logger = get_indented_logger(__name__)

CONFIG_FILE_SEARCH_ORDER = (
    ".bumpversion.cfg",
    ".bumpversion.toml",
    "setup.cfg",
    "pyproject.toml",
)


def find_config_file(explicit_file: Union[str, Path, None] = None) -> Union[Path, None]:
    """
    Find the configuration file, if it exists.

    If no explicit configuration file is passed, it will search in several files to
    find its configuration.

    Args:
        explicit_file: The configuration file to explicitly use.

    Returns:
        The configuration file path
    """
    search_paths = (
        [Path(explicit_file)] if explicit_file else [Path.cwd().joinpath(path) for path in CONFIG_FILE_SEARCH_ORDER]
    )
    return next(
        (
            cfg_file
            for cfg_file in search_paths
            if cfg_file.exists() and "bumpversion]" in cfg_file.read_text(encoding="utf-8")
        ),
        None,
    )


def read_config_file(config_file: Union[str, Path, None] = None) -> Dict[str, Any]:
    """
    Read the configuration file, if it exists.

    If no explicit configuration file is passed, it will search in several files to
    find its configuration.

    Args:
        config_file: The configuration file to explicitly use.

    Returns:
        A dictionary of read key-values
    """
    if not config_file:
        logger.info("No configuration file found.")
        return {}

    config_path = Path(config_file)
    if not config_path.exists():
        logger.info("Configuration file not found: %s.", config_path)
        return {}

    logger.info("Reading config file: %s", config_file)

    if config_path.suffix == ".cfg":
        print_warning("The .cfg file format is deprecated. Please use .toml instead.")
        return read_ini_file(config_path)
    elif config_path.suffix == ".toml":
        return read_toml_file(config_path)
    else:
        logger.info("Unknown config file suffix: %s. Using defaults.", config_path.suffix)
        return {}


def read_toml_file(file_path: Path) -> Dict[str, Any]:
    """
    Parse a TOML file and return the `bumpversion` section.

    Args:
        file_path: The path to the TOML file.

    Returns:
        dict: A dictionary of the `bumpversion` section.
    """
    import tomlkit

    # Load the TOML file
    toml_data = tomlkit.parse(file_path.read_text(encoding="utf-8")).unwrap()

    return toml_data.get("tool", {}).get("bumpversion", {})


def update_config_file(
    config_file: Union[str, Path],
    config: Config,
    current_version: Version,
    new_version: Version,
    context: MutableMapping,
    dry_run: bool = False,
) -> None:
    """
    Update the current_version key in the configuration file.

    Args:
        config_file: The configuration file to explicitly use.
        config: The configuration to use.
        current_version: The current version.
        new_version: The new version.
        context: The context to use for serialization.
        dry_run: True if the update should be a dry run.
    """
    from bumpversion.config.models import FileChange
    from bumpversion.files import DataFileUpdater

    if not config_file:
        logger.info("\n%sNo configuration file found to update.", logger.indent_str)
        return
    else:
        logger.info("\n%sProcessing config file: %s", logger.indent_str, config_file)
    logger.indent()
    config_path = Path(config_file)

    if config.scm_info.tool and not config.scm_info.path_in_repo(config_path):
        logger.info("\n%sConfiguration file is outside of the repo. Not going to change.", logger.indent_str)
        return

    if config_path.suffix != ".toml":
        logger.info("You must have a `.toml` suffix to update the config file: %s.", config_path)
        return

    # TODO: Eventually this should be transformed into another default "files_to_modify" entry
    datafile_config = FileChange(
        filename=str(config_path),
        key_path="tool.bumpversion.current_version",
        search=config.search,
        replace=config.replace,
        regex=config.regex,
        ignore_missing_version=True,
        ignore_missing_file=True,
        serialize=config.serialize,
        parse=config.parse,
    )

    updater = DataFileUpdater(datafile_config, config.version_config.part_configs)
    updater.update_file(current_version, new_version, context, dry_run)
    logger.dedent()
