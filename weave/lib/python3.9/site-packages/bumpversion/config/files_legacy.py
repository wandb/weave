"""This module handles the legacy config file format."""

from __future__ import annotations

import re
from difflib import context_diff
from pathlib import Path
from typing import Any, Dict, Union

from bumpversion.ui import get_indented_logger

logger = get_indented_logger(__name__)


def read_ini_file(file_path: Path) -> Dict[str, Any]:  # noqa: C901
    """
    Parse an INI file and return a dictionary of sections and their options.

    Args:
        file_path: The path to the INI file.

    Returns:
        dict: A dictionary of sections and their options.
    """
    import configparser

    from bumpversion import autocast

    # Create a ConfigParser object and read the INI file
    config_parser = configparser.RawConfigParser()
    if file_path.name == "setup.cfg":
        config_parser = configparser.ConfigParser()

    config_parser.read(file_path)

    # Create an empty dictionary to hold the parsed sections and options
    bumpversion_options: Dict[str, Any] = {"files": [], "parts": {}}

    # Loop through each section in the INI file
    for section_name in config_parser.sections():
        if not section_name.startswith("bumpversion"):
            continue

        section_parts = section_name.split(":")
        num_parts = len(section_parts)
        options = {key: autocast.autocast_value(val) for key, val in config_parser.items(section_name)}
        if "current_version" in options:
            options["current_version"] = str(options["current_version"])

        if num_parts == 1:  # bumpversion section
            bumpversion_options.update(options)
            serialize = bumpversion_options.get("serialize", [])
            if "message" in bumpversion_options and isinstance(bumpversion_options["message"], list):
                bumpversion_options["message"] = ",".join(bumpversion_options["message"])
            if not isinstance(serialize, list):
                bumpversion_options["serialize"] = [serialize]
        elif num_parts > 1 and section_parts[1].startswith("file"):
            file_options = {
                "filename": section_parts[2],
            }
            file_options.update(options)
            if "search" in file_options and isinstance(file_options["search"], list):
                file_options["search"] = "\n".join(file_options["search"])
            if "replace" in file_options and isinstance(file_options["replace"], list):
                file_options["replace"] = "\n".join(file_options["replace"])
            bumpversion_options["files"].append(file_options)
        elif num_parts > 1 and section_parts[1].startswith("glob"):
            file_options = {
                "glob": section_parts[2],
            }
            file_options.update(options)
            if "search" in file_options and isinstance(file_options["search"], list):
                file_options["search"] = "\n".join(file_options["search"])
            if "replace" in file_options and isinstance(file_options["replace"], list):
                file_options["replace"] = "\n".join(file_options["replace"])
            bumpversion_options["files"].append(file_options)
        elif num_parts > 1 and section_parts[1].startswith("part"):
            bumpversion_options["parts"][section_parts[2]] = options

    # Return the dictionary of sections and options
    return bumpversion_options


def update_ini_config_file(
    config_file: Union[str, Path], current_version: str, new_version: str, dry_run: bool = False
) -> None:
    """
    Update the current_version key in the configuration file.

    Instead of parsing and re-writing the config file with new information, it will use
    a regular expression to just replace the current_version value. The idea is it will
    avoid unintentional changes (like formatting) to the config file.

    Args:
        config_file: The configuration file to explicitly use.
        current_version: The serialized current version.
        new_version: The serialized new version.
        dry_run: True if the update should be a dry run.
    """
    cfg_current_version_regex = re.compile(
        f"(?P<section_prefix>\\[bumpversion]\n[^[]*current_version\\s*=\\s*)(?P<version>{current_version})",
        re.MULTILINE,
    )

    config_path = Path(config_file)
    existing_config = config_path.read_text(encoding="utf-8")
    if config_path.suffix == ".cfg" and cfg_current_version_regex.search(existing_config):
        sub_str = f"\\g<section_prefix>{new_version}"
        new_config = cfg_current_version_regex.sub(sub_str, existing_config)
    else:
        logger.info("Could not find the current version in the config file: %s.", config_path)
        return

    logger.info(
        "%s to config file %s:",
        "Would write" if dry_run else "Writing",
        config_path,
    )

    logger.info(
        "\n".join(
            list(
                context_diff(
                    existing_config.splitlines(),
                    new_config.splitlines(),
                    fromfile=f"before {config_path}",
                    tofile=f"after {config_path}",
                    lineterm="",
                )
            )
        )
    )

    if not dry_run:
        config_path.write_text(new_config, encoding="utf-8")
