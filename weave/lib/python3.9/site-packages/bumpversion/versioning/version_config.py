"""Module for managing Versions and their internal parts."""

import re
from typing import Any, Dict, List, MutableMapping, Optional, Tuple

from click import UsageError

from bumpversion.exceptions import BumpVersionError
from bumpversion.ui import get_indented_logger
from bumpversion.utils import labels_for_format
from bumpversion.versioning.models import Version, VersionComponentSpec, VersionSpec
from bumpversion.versioning.serialization import parse_version, serialize

logger = get_indented_logger(__name__)


class VersionConfig:
    """
    Hold a complete representation of a version string.
    """

    def __init__(
        self,
        parse: str,
        serialize: Tuple[str],
        search: str,
        replace: str,
        part_configs: Optional[Dict[str, VersionComponentSpec]] = None,
    ):
        try:
            self.parse_regex = re.compile(parse, re.VERBOSE)
        except re.error as e:
            raise UsageError(f"'{parse}' is not a valid regex.") from e

        self.serialize_formats = serialize
        self.part_configs = part_configs or {}
        self.version_spec = VersionSpec(self.part_configs)
        # TODO: I think these two should be removed from the config object
        self.search = search
        self.replace = replace

    def __repr__(self) -> str:  # pragma: no-coverage
        return f"<bumpversion.VersionConfig:{self.parse_regex.pattern}:{self.serialize_formats}>"

    def __eq__(self, other: Any) -> bool:
        return (
            self.parse_regex.pattern == other.parse_regex.pattern
            and self.serialize_formats == other.serialize_formats
            and self.part_configs == other.part_configs
            and self.search == other.search
            and self.replace == other.replace
        )

    @property
    def order(self) -> List[str]:
        """
        Return the order of the labels in a serialization format.

        Currently, order depends on the first given serialization format.
        This seems like a good idea because this should be the most complete format.

        Returns:
            A list of version part labels in the order they should be rendered.
        """
        return labels_for_format(self.serialize_formats[0])

    def parse(self, version_string: Optional[str] = None, raise_error: bool = False) -> Optional[Version]:
        """
        Parse a version string into a Version object.

        Args:
            version_string: Version string to parse
            raise_error: Raise an exception if a version string is invalid

        Returns:
            A Version object representing the string.

        Raises:
            BumpVersionError: If a version string is invalid and raise_error is True.
        """
        parsed = parse_version(version_string, self.parse_regex.pattern)

        if not parsed and raise_error:
            raise BumpVersionError(f"Unable to parse version {version_string} using {self.parse_regex.pattern}")
        elif not parsed:
            return None

        version = self.version_spec.create_version(parsed)
        version.original = version_string
        return version

    def serialize(self, version: Version, context: MutableMapping) -> str:
        """
        Serialize a version to a string.

        Args:
            version: The version to serialize
            context: The context to use when serializing the version

        Returns:
            The serialized version as a string
        """
        return serialize(version, list(self.serialize_formats), context)
