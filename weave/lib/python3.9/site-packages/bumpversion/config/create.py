"""Module for creating a new config file."""

from pathlib import Path
from typing import Tuple

import questionary
from tomlkit import TOMLDocument


def create_configuration(destination: str, prompt: bool) -> TOMLDocument:
    """
    Create a new configuration as a TOMLDocument.

    Args:
        destination: `stdout` or a path to a new or existing file.
        prompt: `True` if the user should be prompted for input.

    Returns:
        The TOMLDocument structure with the updated configuration.
    """
    config, destination_config = get_defaults_from_dest(destination)

    if prompt:
        allow_dirty_default = "(Y/n)" if config["allow_dirty"] else "(y/N)"
        answers = questionary.form(
            current_version=questionary.text("What is the current version?", default=config["current_version"]),
            commit=questionary.confirm(
                "Commit changes made when bumping to version control?", default=config["commit"]
            ),
            allow_dirty=questionary.confirm(
                "Allow dirty working directory when bumping?",
                default=config["allow_dirty"],
                instruction=(
                    "If you are also creating or modifying other files (e.g. a CHANGELOG), say Yes. "
                    f"{allow_dirty_default} "
                ),
            ),
            tag=questionary.confirm("Tag changes made when bumping in version control?", default=config["tag"]),
            commit_args=questionary.text(
                "Any extra arguments to pass to the commit command?",
                default=config["commit_args"] or "",
                instruction="For example, `--no-verify` is useful if you have a pre-commit hook. ",
            ),
        ).ask()
        config.update(answers)

    for key, val in config.items():
        destination_config["tool"]["bumpversion"][key] = val if val is not None else ""

    return destination_config


def get_defaults_from_dest(destination: str) -> Tuple[dict, TOMLDocument]:
    """Get the default configuration and the configuration from the destination."""
    from tomlkit import document, parse

    from bumpversion.config import DEFAULTS

    config = DEFAULTS.copy()
    if Path(destination).exists():
        destination_config = parse(Path(destination).read_text(encoding="utf-8"))
    else:
        destination_config = document()

    destination_config.setdefault("tool", {})
    destination_config["tool"].setdefault("bumpversion", {})
    existing_config = destination_config["tool"]["bumpversion"]
    if existing_config:
        config.update(existing_config)

    project_config = destination_config.get("project", {}).get("version")
    config["current_version"] = config["current_version"] or project_config or "0.1.0"
    del config["scm_info"]
    del config["parts"]
    del config["files"]

    return config, destination_config
