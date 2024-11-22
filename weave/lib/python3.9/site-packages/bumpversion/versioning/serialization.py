"""Functions for serializing and deserializing version objects."""

import re
from copy import copy
from operator import itemgetter
from typing import Dict, List, MutableMapping

from bumpversion.exceptions import BumpVersionError, FormattingError
from bumpversion.ui import get_indented_logger
from bumpversion.utils import key_val_string, labels_for_format
from bumpversion.versioning.models import Version

logger = get_indented_logger(__name__)


def parse_version(version_string: str, parse_pattern: str) -> Dict[str, str]:
    """
    Parse a version string into a dictionary of the parts and values using a regular expression.

    Args:
        version_string: Version string to parse
        parse_pattern: The regular expression pattern to use for parsing

    Returns:
        A dictionary of version part labels and their values, or an empty dictionary
        if the version string doesn't match.

    Raises:
        BumpVersionError: If the parse_pattern is not a valid regular expression
    """
    if not version_string:
        logger.debug("Version string is empty, returning empty dict")
        return {}
    elif not parse_pattern:
        logger.debug("Parse pattern is empty, returning empty dict")
        return {}

    logger.debug("Parsing version '%s' using regexp '%s'", version_string, parse_pattern)
    logger.indent()

    try:
        pattern = re.compile(parse_pattern, re.VERBOSE)
    except re.error as e:
        raise BumpVersionError(f"'{parse_pattern}' is not a valid regular expression.") from e

    match = re.search(pattern, version_string)

    if not match:
        logger.debug(
            "'%s' does not parse current version '%s'",
            parse_pattern,
            version_string,
        )
        return {}

    parsed = match.groupdict(default="")
    logger.debug("Parsed the following values: %s", key_val_string(parsed))
    logger.dedent()

    return parsed


def multisort(xs: list, specs: tuple) -> list:
    """
    Sort a list of dictionaries by multiple keys.

    From https://docs.python.org/3/howto/sorting.html#sort-stability-and-complex-sorts

    Args:
        xs: The list of dictionaries to sort
        specs: A tuple of (key, reverse) pairs

    Returns:
        The sorted list
    """
    for key, reverse in reversed(specs):
        xs.sort(key=itemgetter(key), reverse=reverse)
    return xs


def serialize(version: Version, serialize_patterns: List[str], context: MutableMapping) -> str:
    """
    Attempts to serialize a version with the given serialization format.

    - valid serialization patterns are those that are renderable with the given context
    - formats that contain all required components are preferred
    - the shortest valid serialization pattern is used
    - if two patterns are equally short, the first one is used
    - if no valid serialization pattern is found, an error is raised

    Args:
        version: The version to serialize
        serialize_patterns: The serialization format to use, using Python's format string syntax
        context: The context to use when serializing the version

    Raises:
        FormattingError: if a serialization pattern

    Returns:
        The serialized version as a string
    """
    logger.debug("Serializing version '%s'", version)
    logger.indent()

    local_context = copy(context)
    local_context.update(version.values())
    local_context_keys = set(local_context.keys())
    required_component_labels = set(version.required_components())

    patterns = []
    for index, pattern in enumerate(serialize_patterns):
        labels = set(labels_for_format(pattern))
        patterns.append(
            {
                "pattern": pattern,
                "labels": labels,
                "order": index,
                "num_labels": len(labels),
                "renderable": local_context_keys >= labels,
                "has_required_components": required_component_labels <= labels,
            }
        )

    valid_patterns = filter(itemgetter("renderable"), patterns)
    sorted_patterns = multisort(
        list(valid_patterns), (("has_required_components", True), ("num_labels", False), ("order", False))
    )

    if not sorted_patterns:
        raise FormattingError(f"Could not find a valid serialization format in {serialize_patterns!r} for {version!r}")

    chosen_pattern = sorted_patterns[0]["pattern"]
    logger.debug("Using serialization format '%s'", chosen_pattern)
    serialized = chosen_pattern.format(**local_context)
    logger.debug("Serialized to '%s'", serialized)
    logger.dedent()

    return serialized
