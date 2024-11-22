"""Methods for changing files."""

import os.path
import re
from copy import deepcopy
from difflib import context_diff
from pathlib import Path
from typing import Dict, List, MutableMapping, Optional

from bumpversion.config.models import FileChange
from bumpversion.exceptions import VersionNotFoundError
from bumpversion.ui import get_indented_logger
from bumpversion.utils import get_nested_value, set_nested_value
from bumpversion.versioning.models import Version, VersionComponentSpec
from bumpversion.versioning.version_config import VersionConfig

logger = get_indented_logger(__name__)


def contains_pattern(search: re.Pattern, contents: str) -> bool:
    """Does the search pattern match any part of the contents?"""
    if not search or not contents:
        return False

    for m in re.finditer(search, contents):
        line_no = contents.count("\n", 0, m.start(0)) + 1
        logger.info(
            "Found '%s' at line %s: %s",
            search.pattern,
            line_no,
            m.string[m.start() : m.end(0)],
        )
        return True
    return False


def log_changes(file_path: str, file_content_before: str, file_content_after: str, dry_run: bool = False) -> None:
    """
    Log the changes that would be made to the file.

    Args:
        file_path: The path to the file
        file_content_before: The file contents before the change
        file_content_after: The file contents after the change
        dry_run: True if this is a report-only job
    """
    if file_content_before != file_content_after:
        logger.info("%s file %s:", "Would change" if dry_run else "Changing", file_path)
        logger.indent()
        indent_str = logger.indent_str

        logger.info(
            f"\n{indent_str}".join(
                list(
                    context_diff(
                        file_content_before.splitlines(),
                        file_content_after.splitlines(),
                        fromfile=f"before {file_path}",
                        tofile=f"after {file_path}",
                        lineterm="",
                    )
                )
            ),
        )
        logger.dedent()
    else:
        logger.info("%s file %s", "Would not change" if dry_run else "Not changing", file_path)


class ConfiguredFile:
    """A file to modify in a configured way."""

    def __init__(
        self,
        file_change: FileChange,
        version_config: VersionConfig,
        search: Optional[str] = None,
        replace: Optional[str] = None,
    ) -> None:
        replacements = [replace, file_change.replace, version_config.replace]
        replacement = next((r for r in replacements if r is not None), "")
        self.file_change = FileChange(
            parse=file_change.parse or version_config.parse_regex.pattern,
            serialize=file_change.serialize or version_config.serialize_formats,
            search=search or file_change.search or version_config.search,
            replace=replacement,
            regex=file_change.regex or False,
            ignore_missing_version=file_change.ignore_missing_version or False,
            ignore_missing_file=file_change.ignore_missing_file or False,
            filename=file_change.filename,
            glob=file_change.glob,
            key_path=file_change.key_path,
            include_bumps=file_change.include_bumps,
            exclude_bumps=file_change.exclude_bumps,
        )
        self.version_config = VersionConfig(
            self.file_change.parse,
            self.file_change.serialize,
            self.file_change.search,
            self.file_change.replace,
            version_config.part_configs,
        )
        self._newlines: Optional[str] = None

    def get_file_contents(self) -> str:
        """
        Return the contents of the file.

        Raises:
            FileNotFoundError: if the file doesn't exist

        Returns:
            The contents of the file
        """
        if not os.path.exists(self.file_change.filename):
            raise FileNotFoundError(f"File not found: '{self.file_change.filename}'")  # pragma: no-coverage

        with open(self.file_change.filename, "rt", encoding="utf-8") as f:
            contents = f.read()
            self._newlines = f.newlines[0] if isinstance(f.newlines, tuple) else f.newlines
            return contents

    def write_file_contents(self, contents: str) -> None:
        """Write the contents of the file."""
        if self._newlines is None:
            _ = self.get_file_contents()

        with open(self.file_change.filename, "wt", encoding="utf-8", newline=self._newlines) as f:
            f.write(contents)

    def _contains_change_pattern(
        self, search_expression: re.Pattern, raw_search_expression: str, version: Version, context: MutableMapping
    ) -> bool:
        """
        Does the file contain the change pattern?

        Args:
            search_expression: The compiled search expression
            raw_search_expression: The raw search expression
            version: The version to check, in case it's not the same as the original
            context: The context to use

        Raises:
            VersionNotFoundError: if the version number isn't present in this file.

        Returns:
            True if the version number is in fact present.
        """
        file_contents = self.get_file_contents()
        if contains_pattern(search_expression, file_contents):
            return True

        # The `search` pattern did not match, but the original supplied
        # version number (representing the same version component values) might
        # match instead. This is probably the case if environment variables are used.

        # check whether `search` isn't customized
        search_pattern_is_default = self.file_change.search == self.version_config.search

        if search_pattern_is_default and contains_pattern(re.compile(re.escape(version.original)), file_contents):
            # The original version is present, and we're not looking for something
            # more specific -> this is accepted as a match
            return True

        # version not found
        if self.file_change.ignore_missing_version:
            return False
        raise VersionNotFoundError(f"Did not find '{raw_search_expression}' in file: '{self.file_change.filename}'")

    def make_file_change(
        self, current_version: Version, new_version: Version, context: MutableMapping, dry_run: bool = False
    ) -> None:
        """Make the change to the file."""
        logger.info(
            "\n%sFile %s: replace `%s` with `%s`",
            logger.indent_str,
            self.file_change.filename,
            self.file_change.search,
            self.file_change.replace,
        )
        logger.indent()
        if not os.path.exists(self.file_change.filename):
            if self.file_change.ignore_missing_file:
                logger.info("File not found, but ignoring")
                logger.dedent()
                return
            raise FileNotFoundError(f"File not found: '{self.file_change.filename}'")  # pragma: no-coverage
        context["current_version"] = self._get_serialized_version("current_version", current_version, context)
        if new_version:
            context["new_version"] = self._get_serialized_version("new_version", new_version, context)
        else:
            logger.debug("No new version, using current version as new version")
            context["new_version"] = context["current_version"]

        search_for, raw_search_pattern = self.file_change.get_search_pattern(context)
        replace_with = self.version_config.replace.format(**context)

        if not self._contains_change_pattern(search_for, raw_search_pattern, current_version, context):
            logger.dedent()
            return

        file_content_before = self.get_file_contents()

        file_content_after = search_for.sub(replace_with, file_content_before)

        if file_content_before == file_content_after and current_version.original:
            og_context = deepcopy(context)
            og_context["current_version"] = current_version.original
            search_for_og, _ = self.file_change.get_search_pattern(og_context)
            file_content_after = search_for_og.sub(replace_with, file_content_before)

        log_changes(self.file_change.filename, file_content_before, file_content_after, dry_run)
        logger.dedent()
        if not dry_run:  # pragma: no-coverage
            self.write_file_contents(file_content_after)

    def _get_serialized_version(self, context_key: str, version: Version, context: MutableMapping) -> str:
        """Get the serialized version."""
        logger.debug("Serializing the %s", context_key.replace("_", " "))
        logger.indent()
        serialized_version = self.version_config.serialize(version, context)
        logger.dedent()
        return serialized_version

    def __str__(self) -> str:  # pragma: no-coverage
        return self.file_change.filename

    def __repr__(self) -> str:  # pragma: no-coverage
        return f"<bumpversion.ConfiguredFile:{self.file_change.filename}>"


def resolve_file_config(
    files: List[FileChange], version_config: VersionConfig, search: Optional[str] = None, replace: Optional[str] = None
) -> List[ConfiguredFile]:
    """
    Resolve the files, searching and replacing values according to the FileConfig.

    Args:
        files: A list of file configurations
        version_config: How the version should be changed
        search: The search pattern to use instead of any configured search pattern
        replace: The replace pattern to use instead of any configured replace pattern

    Returns:
        A list of ConfiguredFiles
    """
    return [ConfiguredFile(file_cfg, version_config, search, replace) for file_cfg in files]


def modify_files(
    files: List[ConfiguredFile],
    current_version: Version,
    new_version: Version,
    context: MutableMapping,
    dry_run: bool = False,
) -> None:
    """
    Modify the files, searching and replacing values according to the FileConfig.

    Args:
        files: The list of configured files
        current_version: The current version
        new_version: The next version
        context: The context used for rendering the version
        dry_run: True if this should be a report-only job
    """
    # _check_files_contain_version(files, current_version, context)
    for f in files:
        f.make_file_change(current_version, new_version, context, dry_run)


class FileUpdater:
    """A class to handle updating files."""

    def __init__(
        self,
        file_change: FileChange,
        version_config: VersionConfig,
        search: Optional[str] = None,
        replace: Optional[str] = None,
    ) -> None:
        self.file_change = FileChange(
            parse=file_change.parse or version_config.parse_regex.pattern,
            serialize=file_change.serialize or version_config.serialize_formats,
            search=search or file_change.search or version_config.search,
            replace=replace or file_change.replace or version_config.replace,
            regex=file_change.regex or False,
            ignore_missing_file=file_change.ignore_missing_file or False,
            ignore_missing_version=file_change.ignore_missing_version or False,
            filename=file_change.filename,
            glob=file_change.glob,
            key_path=file_change.key_path,
        )
        self.version_config = VersionConfig(
            self.file_change.parse,
            self.file_change.serialize,
            self.file_change.search,
            self.file_change.replace,
            version_config.part_configs,
        )
        self._newlines: Optional[str] = None

    def update_file(
        self, current_version: Version, new_version: Version, context: MutableMapping, dry_run: bool = False
    ) -> None:
        """Update the files."""
        # TODO: Implement this
        pass


class DataFileUpdater:
    """A class to handle updating files."""

    def __init__(
        self,
        file_change: FileChange,
        version_part_configs: Dict[str, VersionComponentSpec],
    ) -> None:
        self.file_change = file_change
        self.version_config = VersionConfig(
            self.file_change.parse,
            self.file_change.serialize,
            self.file_change.search,
            self.file_change.replace,
            version_part_configs,
        )
        self.path = Path(self.file_change.filename)
        self._newlines: Optional[str] = None

    def update_file(
        self, current_version: Version, new_version: Version, context: MutableMapping, dry_run: bool = False
    ) -> None:
        """Update the files."""
        new_context = deepcopy(context)
        new_context["current_version"] = self.version_config.serialize(current_version, context)
        new_context["new_version"] = self.version_config.serialize(new_version, context)
        search_for, raw_search_pattern = self.file_change.get_search_pattern(new_context)
        replace_with = self.file_change.replace.format(**new_context)
        if self.path.suffix == ".toml":
            try:
                self._update_toml_file(search_for, raw_search_pattern, replace_with, dry_run)
            except KeyError as e:
                if self.file_change.ignore_missing_file or self.file_change.ignore_missing_version:
                    pass
                else:
                    raise e

    def _update_toml_file(
        self, search_for: re.Pattern, raw_search_pattern: str, replace_with: str, dry_run: bool = False
    ) -> None:
        """Update a TOML file."""
        import tomlkit

        toml_data = tomlkit.parse(self.path.read_text(encoding="utf-8"))
        value_before = get_nested_value(toml_data, self.file_change.key_path)

        if not contains_pattern(search_for, value_before) and not self.file_change.ignore_missing_version:
            raise ValueError(
                f"Key '{self.file_change.key_path}' in {self.path} does not contain the correct contents: "
                f"{raw_search_pattern}"
            )

        new_value = search_for.sub(replace_with, value_before)
        log_changes(f"{self.path}:{self.file_change.key_path}", value_before, new_value, dry_run)

        if dry_run:
            return

        set_nested_value(toml_data, new_value, self.file_change.key_path)

        self.path.write_text(tomlkit.dumps(toml_data), encoding="utf-8")
