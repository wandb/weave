"""Bump My Version configuration models."""

from __future__ import annotations

import re
from collections import defaultdict
from itertools import chain
from typing import TYPE_CHECKING, Dict, List, MutableMapping, Optional, Tuple, Union

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from bumpversion.ui import get_indented_logger
from bumpversion.versioning.models import VersionComponentSpec  # NOQA: TCH001

if TYPE_CHECKING:
    from bumpversion.scm import SCMInfo
    from bumpversion.versioning.models import VersionSpec
    from bumpversion.versioning.version_config import VersionConfig

logger = get_indented_logger(__name__)


class FileChange(BaseModel):
    """A change to make to a file."""

    parse: str
    serialize: tuple
    search: str
    replace: str
    regex: bool
    ignore_missing_version: bool
    ignore_missing_file: bool
    filename: Optional[str] = None
    glob: Optional[str] = None  # Conflicts with filename. If both are specified, glob wins
    glob_exclude: Optional[tuple] = None
    key_path: Optional[str] = None  # If specified, and has an appropriate extension, will be treated as a data file
    include_bumps: Optional[tuple] = None
    exclude_bumps: tuple = Field(default_factory=tuple)

    def __hash__(self):
        """Return a hash of the model."""
        return hash(tuple(sorted(self.model_dump().items())))

    def get_search_pattern(self, context: MutableMapping) -> Tuple[re.Pattern, str]:
        """
        Render the search pattern and return the compiled regex pattern and the raw pattern.

        Args:
            context: The context to use for rendering the search pattern

        Returns:
            A tuple of the compiled regex pattern and the raw pattern as a string.
        """
        logger.debug("Rendering search pattern with context")
        logger.indent()
        # the default search pattern is escaped, so we can still use it in a regex
        raw_pattern = self.search.format(**context)
        default = re.compile(re.escape(raw_pattern), re.MULTILINE | re.DOTALL)
        if not self.regex:
            logger.debug("No RegEx flag detected. Searching for the default pattern: '%s'", default.pattern)
            logger.dedent()
            return default, raw_pattern

        re_context = {key: re.escape(str(value)) for key, value in context.items()}
        regex_pattern = self.search.format(**re_context)
        try:
            search_for_re = re.compile(regex_pattern, re.MULTILINE | re.DOTALL)
            logger.debug("Searching for the regex: '%s'", search_for_re.pattern)
            logger.dedent()
            return search_for_re, raw_pattern
        except re.error as e:
            logger.error("Invalid regex '%s': %s.", default, e)

        logger.debug("Invalid regex. Searching for the default pattern: '%s'", raw_pattern)
        logger.dedent()

        return default, raw_pattern


class Config(BaseSettings):
    """Bump Version configuration."""

    current_version: Optional[str]
    parse: str
    serialize: tuple = Field(min_length=1)
    search: str
    replace: str
    regex: bool
    ignore_missing_version: bool
    ignore_missing_files: bool
    tag: bool
    sign_tags: bool
    tag_name: str
    tag_message: Optional[str]
    allow_dirty: bool
    commit: bool
    message: str
    commit_args: Optional[str]
    scm_info: Optional["SCMInfo"]
    parts: Dict[str, VersionComponentSpec]
    files: List[FileChange] = Field(default_factory=list)
    setup_hooks: List[str] = Field(default_factory=list)
    pre_commit_hooks: List[str] = Field(default_factory=list)
    post_commit_hooks: List[str] = Field(default_factory=list)
    included_paths: List[str] = Field(default_factory=list)
    excluded_paths: List[str] = Field(default_factory=list)
    model_config = SettingsConfigDict(env_prefix="bumpversion_")
    _resolved_filemap: Optional[Dict[str, List[FileChange]]] = None

    def add_files(self, filename: Union[str, List[str]]) -> None:
        """Add a filename to the list of files."""
        filenames = [filename] if isinstance(filename, str) else filename
        files = set(self.files)
        for name in filenames:
            files.add(
                FileChange(
                    filename=name,
                    glob=None,
                    key_path=None,
                    parse=self.parse,
                    serialize=self.serialize,
                    search=self.search,
                    replace=self.replace,
                    regex=self.regex,
                    ignore_missing_version=self.ignore_missing_version,
                    ignore_missing_file=self.ignore_missing_files,
                    include_bumps=tuple(self.parts.keys()),
                )
            )
        self.files = list(files)

        self._resolved_filemap = None

    @property
    def resolved_filemap(self) -> Dict[str, List[FileChange]]:
        """Return the cached resolved filemap."""
        if self._resolved_filemap is None:
            self._resolved_filemap = self._resolve_filemap()
        return self._resolved_filemap

    def _resolve_filemap(self) -> Dict[str, List[FileChange]]:
        """Return a map of filenames to file configs, expanding any globs."""
        from bumpversion.config.utils import resolve_glob_files

        output = defaultdict(list)
        new_files = []
        for file_cfg in self.files:
            if file_cfg.glob:
                new_files.extend(resolve_glob_files(file_cfg))
            else:
                new_files.append(file_cfg)

        for file_cfg in new_files:
            output[file_cfg.filename].append(file_cfg)
        return output

    @property
    def files_to_modify(self) -> List[FileChange]:
        """Return a list of files to modify."""
        files_not_excluded = [filename for filename in self.resolved_filemap if filename not in self.excluded_paths]
        inclusion_set = set(self.included_paths) | set(files_not_excluded)
        return list(
            chain.from_iterable(
                file_cfg_list for key, file_cfg_list in self.resolved_filemap.items() if key in inclusion_set
            )
        )

    @property
    def version_config(self) -> "VersionConfig":
        """Return the version configuration."""
        from bumpversion.versioning.version_config import VersionConfig

        return VersionConfig(self.parse, self.serialize, self.search, self.replace, self.parts)

    def version_spec(self, version: Optional[str] = None) -> "VersionSpec":
        """Return the version specification."""
        from bumpversion.versioning.models import VersionSpec

        return VersionSpec(self.parts)
