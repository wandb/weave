"""Helper functions for the config module."""

from __future__ import annotations

import re
from typing import Dict, List

from wcmatch import glob

from bumpversion.config.models import FileChange
from bumpversion.exceptions import BumpVersionError
from bumpversion.versioning.models import VersionComponentSpec


def get_all_file_configs(config_dict: dict) -> List[FileChange]:
    """Make sure all version components are included."""
    defaults = {
        "parse": config_dict["parse"],
        "serialize": config_dict["serialize"],
        "search": config_dict["search"],
        "replace": config_dict["replace"],
        "ignore_missing_version": config_dict["ignore_missing_version"],
        "ignore_missing_file": config_dict["ignore_missing_files"],
        "regex": config_dict["regex"],
        "include_bumps": tuple(config_dict["parts"]),
    }
    files = [{k: v for k, v in filecfg.items() if v is not None} for filecfg in config_dict["files"]]
    for f in files:
        f.update({k: v for k, v in defaults.items() if k not in f})
    return [FileChange(**f) for f in files]


def get_all_part_configs(config_dict: dict) -> Dict[str, VersionComponentSpec]:
    """Make sure all version components are included."""
    try:
        parsing_groups = list(re.compile(config_dict["parse"]).groupindex.keys())
    except re.error as e:
        raise BumpVersionError(f"Could not parse regex '{config_dict['parse']}': {e}") from e
    parts = config_dict["parts"]

    part_configs = {}
    for label in parsing_groups:
        is_independent = label.startswith("$")
        part_configs[label] = (
            VersionComponentSpec(**parts[label])
            if label in parts
            else VersionComponentSpec(independent=is_independent)
        )
    return part_configs


def resolve_glob_files(file_cfg: FileChange) -> List[FileChange]:
    """
    Return a list of file configurations that match the glob pattern.

    Args:
        file_cfg: The file configuration containing the glob pattern

    Returns:
        A list of resolved file configurations according to the pattern.
    """
    files: List[FileChange] = []
    exclude = file_cfg.glob_exclude or ()
    glob_flags = glob.GLOBSTAR | glob.FORCEUNIX | glob.SPLIT
    for filename_glob in glob.glob(file_cfg.glob, flags=glob_flags, exclude=exclude):
        new_file_cfg = file_cfg.model_copy()
        new_file_cfg.filename = filename_glob
        new_file_cfg.glob = None
        files.append(new_file_cfg)
    return files
